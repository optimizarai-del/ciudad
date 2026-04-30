"""
Integración Tokko Broker.
Configurar en .env:
  TOKKO_API_KEY=tu_api_key
  TOKKO_API_URL=https://www.tokkosoftware.com/api/v1  (opcional)
"""
import os
from datetime import datetime
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models

router = APIRouter(prefix="/api/tokko", tags=["tokko"])

TOKKO_KEY = os.getenv("TOKKO_API_KEY", "")
TOKKO_URL = os.getenv("TOKKO_API_URL", "https://www.tokkosoftware.com/api/v1")


@router.get("/status")
def status(user=Depends(get_current_user)):
    return {"configurado": bool(TOKKO_KEY), "url": TOKKO_URL}


@router.get("/preview")
async def preview(user=Depends(get_current_user), db: Session = Depends(get_db)):
    if not TOKKO_KEY:
        raise HTTPException(400, "TOKKO_API_KEY no configurada en el archivo .env del backend.")

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(
                f"{TOKKO_URL}/property/search/",
                params={"key": TOKKO_KEY, "format": "json", "limit": 50, "lang": "es"},
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(502, f"Tokko respondió {e.response.status_code}")
        except httpx.RequestError as e:
            raise HTTPException(502, f"No se pudo conectar con Tokko: {e}")

    propiedades = []
    tokko_ids_existentes = {
        p.tokko_id
        for p in db.query(models.Propiedad.tokko_id).filter(models.Propiedad.tokko_id.isnot(None)).all()
    }

    for item in data.get("objects", []):
        tid = str(item.get("id", ""))
        ops = item.get("operations") or []
        precio = 0
        if ops:
            prices = ops[0].get("prices") or []
            precio = prices[0].get("price", 0) if prices else 0

        propiedades.append({
            "tokko_id": tid,
            "direccion": item.get("address") or "Sin dirección",
            "tipo": _map_tipo(item.get("type", {}).get("code", "")),
            "ciudad": (item.get("location") or {}).get("name", ""),
            "precio_alquiler": precio,
            "superficie_m2": item.get("surface_total") or 0,
            "ambientes": item.get("room_amount") or 0,
            "descripcion": (item.get("description") or "")[:300],
            "ya_importada": tid in tokko_ids_existentes,
        })

    return {"total": len(propiedades), "propiedades": propiedades}


@router.post("/sync")
async def sync(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not TOKKO_KEY:
        raise HTTPException(400, "TOKKO_API_KEY no configurada en el archivo .env del backend.")

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            r = await client.get(
                f"{TOKKO_URL}/property/search/",
                params={"key": TOKKO_KEY, "format": "json", "limit": 200, "lang": "es"},
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(502, f"Tokko respondió {e.response.status_code}")
        except httpx.RequestError as e:
            raise HTTPException(502, f"No se pudo conectar con Tokko: {e}")

    importadas = 0
    actualizadas = 0

    for item in data.get("objects", []):
        tid = str(item.get("id", ""))
        ops = item.get("operations") or []
        precio = 0
        if ops:
            prices = ops[0].get("prices") or []
            precio = prices[0].get("price", 0) if prices else 0

        datos = dict(
            direccion=item.get("address") or "Sin dirección",
            tipo=_map_tipo(item.get("type", {}).get("code", "")),
            ciudad=(item.get("location") or {}).get("name", ""),
            precio_alquiler=float(precio or 0),
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
        else:
            nueva = models.Propiedad(tokko_id=tid, **datos)
            db.add(nueva)
            importadas += 1

    db.commit()
    return {
        "ok": True,
        "importadas": importadas,
        "actualizadas": actualizadas,
        "total": importadas + actualizadas,
    }


def _map_tipo(code: str) -> str:
    mapa = {
        "Departamento": "departamento",
        "Casa": "casa",
        "Local Comercial": "local",
        "Campo": "campo",
        "Oficina": "local",
        "PH": "departamento",
    }
    return mapa.get(code, "departamento")
