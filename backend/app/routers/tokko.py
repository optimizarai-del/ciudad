"""
Integración Tokko Broker.

Tokko es nuestro feed de propiedades en VENTA — nunca alquileres. Las
propiedades importadas se marcan como modalidad=venta automáticamente.

Configurar en .env:
  TOKKO_API_KEY=tu_api_key
  TOKKO_API_URL=https://www.tokkobroker.com/api/v1  (opcional)
"""
import asyncio
import base64
import os
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models

router = APIRouter(prefix="/api/tokko", tags=["tokko"])

TOKKO_KEY = os.getenv("TOKKO_API_KEY", "")
# Dominio actual de Tokko (la marca antigua tokkosoftware.com está deprecada).
TOKKO_URL = os.getenv("TOKKO_API_URL", "https://www.tokkobroker.com/api/v1")

# Tope de fotos a importar por propiedad (las primeras N por `order`).
MAX_FOTOS_POR_PROP = 8


def _map_tipo(code: str) -> str:
    """Mapeo de tipos Tokko → enum interno PropiedadTipo."""
    mapa = {
        "Departamento": "departamento",
        "Casa": "casa",
        "Local Comercial": "local",
        "Local": "local",
        "Oficina": "local",
        "PH": "departamento",
        "Campo": "campo",
        "Terreno": "campo",       # Sin enum específico → asimilamos a campo
        "Lote": "campo",
        "Cochera": "local",
    }
    nombre = code or ""
    return mapa.get(nombre, "departamento")


def _precio_venta(item: dict) -> tuple[float, str]:
    """
    Tokko trae operations[].prices[]. Para venta priorizamos USD; si no hay
    USD tomamos lo que venga.
    """
    for op in item.get("operations") or []:
        if str(op.get("operation_type") or "").lower() != "venta":
            continue
        prices = op.get("prices") or []
        if not prices:
            continue
        usd = next((p for p in prices if (p.get("currency") or "").upper() == "USD"), None)
        chosen = usd or prices[0]
        return float(chosen.get("price") or 0), chosen.get("currency") or ""
    # Si no hay operación 'Venta' explícita, devolver 0
    return 0.0, ""


@router.get("/status")
def status(user=Depends(get_current_user)):
    return {"configurado": bool(TOKKO_KEY), "url": TOKKO_URL}


@router.get("/propiedades")
def listar_sincronizadas(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Lista las propiedades que ya fueron importadas desde Tokko (tokko_id no nulo)."""
    rows = (
        db.query(models.Propiedad)
        .filter(models.Propiedad.tokko_id.isnot(None))
        .filter(models.Propiedad.tokko_id != "")
        .order_by(models.Propiedad.id.desc())
        .all()
    )
    return [
        {
            "id": p.id,
            "tokko_id": p.tokko_id,
            "codigo": p.codigo,
            "direccion": p.direccion,
            "ciudad": p.ciudad,
            "tipo": p.tipo.value if hasattr(p.tipo, "value") else p.tipo,
            "modalidad": p.modalidad.value if hasattr(p.modalidad, "value") else p.modalidad,
            "estado": p.estado.value if hasattr(p.estado, "value") else p.estado,
            "ambientes": p.ambientes,
            "superficie_m2": p.superficie_m2,
            "precio_alquiler": p.precio_alquiler,
            "precio_venta": p.precio_venta,
            "tokko_sync_at": p.tokko_sync_at.isoformat() if p.tokko_sync_at else None,
        }
        for p in rows
    ]


@router.get("/preview")
async def preview(user=Depends(get_current_user), db: Session = Depends(get_db)):
    if not TOKKO_KEY:
        raise HTTPException(400, "TOKKO_API_KEY no configurada en el archivo .env del backend.")

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(
                f"{TOKKO_URL}/property/",
                params={"key": TOKKO_KEY, "format": "json", "limit": 50, "lang": "es_ar"},
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(502, f"Tokko respondió {e.response.status_code}: {e.response.text[:200]}")
        except httpx.RequestError as e:
            raise HTTPException(502, f"No se pudo conectar con Tokko: {e}")

    propiedades = []
    tokko_ids_existentes = {
        p.tokko_id
        for p in db.query(models.Propiedad.tokko_id).filter(models.Propiedad.tokko_id.isnot(None)).all()
    }

    for item in data.get("objects", []):
        tid = str(item.get("id", ""))
        precio_v, moneda = _precio_venta(item)
        propiedades.append({
            "tokko_id": tid,
            "direccion": item.get("address") or "Sin dirección",
            "tipo": _map_tipo((item.get("type") or {}).get("name", "")),
            "ciudad": (item.get("location") or {}).get("name", ""),
            "precio_venta": precio_v,
            "moneda": moneda,
            "superficie_m2": item.get("surface_total") or 0,
            "ambientes": item.get("room_amount") or 0,
            "fotos_disponibles": len(item.get("photos") or []),
            "descripcion": (item.get("description") or "")[:300],
            "ya_importada": tid in tokko_ids_existentes,
        })

    return {"total": len(propiedades), "propiedades": propiedades}


async def _descargar_foto(client: httpx.AsyncClient, url: str) -> Optional[bytes]:
    try:
        r = await client.get(url, timeout=20.0)
        if r.status_code == 200:
            return r.content
    except Exception:
        pass
    return None


async def _sync_fotos_propiedad(db: Session, prop: models.Propiedad, photos: list[dict],
                                client: httpx.AsyncClient, force: bool = False) -> int:
    """
    Importa hasta MAX_FOTOS_POR_PROP fotos de Tokko como PropiedadAdjunto.
    Idempotente: si la propiedad ya tiene adjuntos con tokko_image_url igual,
    no descarga de nuevo. Devuelve cuántas fotos guardó.
    """
    if not photos:
        return 0

    # Normalizar y ordenar por order, dejar la is_front_cover primera
    photos = sorted(
        photos,
        key=lambda p: (not bool(p.get("is_front_cover")), int(p.get("order") or 999))
    )[:MAX_FOTOS_POR_PROP]

    existentes = db.query(models.PropiedadAdjunto).filter_by(propiedad_id=prop.id).all()
    descripciones_ya = {a.descripcion or "" for a in existentes}

    guardadas = 0
    for ph in photos:
        url = ph.get("image") or ph.get("original")
        if not url:
            continue
        # tag: usamos la URL como descripción para idempotencia
        tag = f"tokko:{url}"
        if tag in descripciones_ya and not force:
            continue
        contenido = await _descargar_foto(client, url)
        if not contenido:
            continue
        # Si supera 8MB lo saltamos (límite del modelo)
        if len(contenido) > 8 * 1024 * 1024:
            continue
        nombre = url.rsplit("/", 1)[-1].split("?")[0] or f"tokko-{prop.tokko_id}.jpg"
        adj = models.PropiedadAdjunto(
            propiedad_id=prop.id,
            tipo=models.AdjuntoTipo.foto,
            nombre_archivo=nombre,
            mime="image/jpeg",
            tamano_bytes=len(contenido),
            descripcion=tag,
            blob_b64=base64.b64encode(contenido).decode("ascii"),
            es_principal=ph.get("is_front_cover") and not any(a.es_principal for a in existentes),
        )
        db.add(adj)
        guardadas += 1
    db.commit()
    return guardadas


@router.post("/sync")
async def sync(
    importar_fotos: bool = True,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not TOKKO_KEY:
        raise HTTPException(400, "TOKKO_API_KEY no configurada en el archivo .env del backend.")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            r = await client.get(
                f"{TOKKO_URL}/property/",
                params={"key": TOKKO_KEY, "format": "json", "limit": 200, "lang": "es_ar"},
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(502, f"Tokko respondió {e.response.status_code}: {e.response.text[:200]}")
        except httpx.RequestError as e:
            raise HTTPException(502, f"No se pudo conectar con Tokko: {e}")

        importadas = 0
        actualizadas = 0
        fotos_total = 0

        for item in data.get("objects", []):
            tid = str(item.get("id", ""))
            precio_v, _ = _precio_venta(item)

            datos = dict(
                direccion=item.get("address") or "Sin dirección",
                tipo=_map_tipo((item.get("type") or {}).get("name", "")),
                ciudad=(item.get("location") or {}).get("name", ""),
                # Tokko = solo VENTA
                modalidad=models.PropiedadModalidad.venta,
                precio_venta=float(precio_v or 0),
                precio_alquiler=0,
                superficie_m2=float(item.get("surface_total") or 0),
                ambientes=int(item.get("room_amount") or 0),
                descripcion=(item.get("description") or "")[:500],
                tokko_sync_at=datetime.utcnow(),
            )

            existente = db.query(models.Propiedad).filter_by(tokko_id=tid).first()
            if existente:
                for k, v in datos.items():
                    setattr(existente, k, v)
                actualizadas += 1
                prop_obj = existente
            else:
                prop_obj = models.Propiedad(tokko_id=tid, **datos)
                db.add(prop_obj)
                importadas += 1
            db.flush()

            if importar_fotos:
                fotos_total += await _sync_fotos_propiedad(
                    db, prop_obj, item.get("photos") or [], client
                )

        db.commit()

    return {
        "ok": True,
        "importadas": importadas,
        "actualizadas": actualizadas,
        "total": importadas + actualizadas,
        "fotos_descargadas": fotos_total,
        "modalidad": "venta (forzada en todas)",
    }
