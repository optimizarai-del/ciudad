"""
Integración Tokko Broker (Fase 2, plan sección 7).

Sincroniza propiedades de la red Tokko hacia el catálogo (fuente=tokko). La
config (api_key + ciudades a sincronizar, Mod #7) vive en ventas_tokko_config.

Degradación elegante: sin api_key configurada, `sincronizar` devuelve un
resultado vacío explicando que falta la config, sin romper. La normalización de
una propiedad Tokko a nuestro modelo está aislada en `_normalizar` para testear.
"""
import json
import urllib.parse
import urllib.request
from datetime import datetime

from sqlalchemy.orm import Session

from app import models_ventas as mv

TOKKO_BASE = "https://www.tokkobroker.com/api/v1/property/"

# Mapeo de tipos Tokko → nuestros tipos
_TIPO_MAP = {
    "casa": mv.VPropiedadTipo.casa,
    "departamento": mv.VPropiedadTipo.departamento,
    "ph": mv.VPropiedadTipo.departamento,
    "terreno": mv.VPropiedadTipo.lote,
    "lote": mv.VPropiedadTipo.lote,
    "local": mv.VPropiedadTipo.local,
    "oficina": mv.VPropiedadTipo.oficina,
    "galpón": mv.VPropiedadTipo.galpon,
    "campo": mv.VPropiedadTipo.campo,
}


def get_config(db: Session) -> mv.VentasTokkoConfig:
    cfg = db.query(mv.VentasTokkoConfig).first()
    if not cfg:
        cfg = mv.VentasTokkoConfig(activo=False, ciudades_json=json.dumps([]))
        db.add(cfg); db.flush()
    return cfg


def _ciudades(cfg) -> list:
    try:
        return json.loads(cfg.ciudades_json) if cfg.ciudades_json else []
    except Exception:
        return []


def _normalizar(raw: dict) -> dict:
    """Convierte una propiedad cruda de Tokko a kwargs de VentasPropiedad."""
    tipo_raw = (raw.get("type", {}) or {}).get("name", "").lower()
    tipo = _TIPO_MAP.get(tipo_raw, mv.VPropiedadTipo.otro)

    # Precio: primera operación de venta en USD si existe
    precio = None
    for op in raw.get("operations", []) or []:
        for pr in op.get("prices", []) or []:
            if (pr.get("currency") or "").upper() == "USD":
                precio = pr.get("price")
                break
        if precio:
            break

    return {
        "titulo": raw.get("publication_title") or raw.get("address"),
        "tipo": tipo,
        "estado": mv.VPropiedadEstado.disponible,
        "fuente": mv.VPropiedadFuente.tokko,
        "direccion": raw.get("address"),
        "ciudad": (raw.get("location", {}) or {}).get("name"),
        "precio_usd": precio,
        "superficie_m2": raw.get("total_surface") or raw.get("roofed_surface"),
        "dormitorios": raw.get("suite_amount") or raw.get("room_amount"),
        "banos": raw.get("bathroom_amount"),
        "descripcion": raw.get("description"),
        "link_externo": raw.get("public_url"),
        "tokko_id": str(raw.get("id")) if raw.get("id") else None,
    }


def _fetch(api_key: str, limit=50) -> list:
    params = urllib.parse.urlencode({"key": api_key, "limit": limit, "format": "json"})
    req = urllib.request.Request(f"{TOKKO_BASE}?{params}")
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    return data.get("objects", data if isinstance(data, list) else [])


def sincronizar(db: Session) -> dict:
    """Trae propiedades de Tokko (filtradas por ciudades) y las upsertea en el
    catálogo. Devuelve un resumen de la corrida (también usado por Mod #4)."""
    cfg = get_config(db)
    if not cfg.activo or not cfg.api_key:
        return {"ok": False, "motivo": "Tokko no configurado (falta api_key o está inactivo).",
                "nuevas": 0, "actualizadas": 0}

    ciudades = [c.lower() for c in _ciudades(cfg)]
    try:
        objetos = _fetch(cfg.api_key)
    except Exception as e:
        resumen = {"ok": False, "motivo": f"Error al consultar Tokko: {e}",
                   "nuevas": 0, "actualizadas": 0}
        cfg.ultima_sync = datetime.utcnow()
        cfg.ultima_sync_resultado = json.dumps(resumen, ensure_ascii=False)
        db.flush()
        return resumen

    nuevas = actualizadas = saltadas = 0
    for raw in objetos:
        norm = _normalizar(raw)
        # Segmentación por ciudad (Mod #7)
        if ciudades and (norm.get("ciudad") or "").lower() not in ciudades:
            saltadas += 1
            continue
        norm.pop("tokko_id", None)
        # Dedup por link_externo (URL pública de Tokko). Solo deduplicamos si
        # hay link Y la propiedad existente también es de fuente Tokko, para no
        # pisar nunca una propiedad cargada a mano con link vacío/igual.
        existente = None
        link = norm.get("link_externo")
        if link:
            existente = (db.query(mv.VentasPropiedad)
                         .filter_by(link_externo=link, fuente=mv.VPropiedadFuente.tokko).first())
        if existente:
            for k, val in norm.items():
                setattr(existente, k, val)
            actualizadas += 1
        else:
            db.add(mv.VentasPropiedad(**norm))
            nuevas += 1
    db.flush()

    resumen = {"ok": True, "nuevas": nuevas, "actualizadas": actualizadas,
               "saltadas_por_ciudad": saltadas, "total_recibidas": len(objetos)}
    cfg.ultima_sync = datetime.utcnow()
    cfg.ultima_sync_resultado = json.dumps(resumen, ensure_ascii=False)
    db.flush()
    return resumen
