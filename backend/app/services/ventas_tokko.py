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

def _map_tipo(type_obj: dict) -> "mv.VPropiedadTipo":
    """Mapea el tipo de Tokko (viene en inglés: 'House', 'Apartment'...) a
    nuestro enum. Tolerante: matchea por substring sobre el name en minúsculas,
    con fallback por code."""
    name = (type_obj or {}).get("name", "").lower()
    code = (type_obj or {}).get("code", "").upper()
    # Orden importa: chequear los más específicos primero.
    if "country" in name or "farm" in name or "ranch" in name or "chacra" in name or "campo" in name:
        return mv.VPropiedadTipo.campo
    if "warehouse" in name or "galp" in name or code == "WH":
        return mv.VPropiedadTipo.galpon
    if "apart" in name or "condo" in name or "ph" in name or code in ("AP", "PH"):
        return mv.VPropiedadTipo.departamento
    if "house" in name or code == "HO":
        return mv.VPropiedadTipo.casa
    if "land" in name or "lot" in name or "terreno" in name or code in ("LA", "LO"):
        return mv.VPropiedadTipo.lote
    if "office" in name or "oficina" in name or code == "OF":
        return mv.VPropiedadTipo.oficina
    if "commercial" in name or "store" in name or "local" in name or "business" in name:
        return mv.VPropiedadTipo.local
    return mv.VPropiedadTipo.otro


def _ciudad_de_location(loc: dict, ciudades_cfg: list):
    """Extrae la ciudad de `full_location` ("Argentina | La Pampa | Capital |
    Santa Rosa | Centro"). Si alguna ciudad configurada aparece en la cadena,
    devuelve esa (alineado con el filtro); si no, una heurística por jerarquía.
    Devuelve (ciudad, full_location_lower)."""
    full = (loc or {}).get("full_location") or (loc or {}).get("short_location") or ""
    full_low = full.lower()
    for c in ciudades_cfg:
        if c.lower() in full_low:
            return c, full_low
    # Heurística: en "País | Provincia | Depto | Ciudad | Barrio" la ciudad
    # suele ser el penúltimo o antepenúltimo segmento.
    partes = [p.strip() for p in full.split("|") if p.strip()]
    if len(partes) >= 2:
        ciudad = partes[-2] if len(partes) >= 4 else partes[-1]
    else:
        ciudad = (loc or {}).get("name")
    return ciudad, full_low


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


def _to_float(v):
    try:
        return float(v) if v not in (None, "", "0", 0) else None
    except (ValueError, TypeError):
        return None


def _to_int(v):
    try:
        return int(v) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


def _normalizar(raw: dict, ciudades_cfg=None) -> dict:
    """Convierte una propiedad cruda de Tokko a kwargs de VentasPropiedad.
    Marca `_es_venta` y `_full_location` (transitorios, se popean antes de
    persistir)."""
    ciudades_cfg = ciudades_cfg or []
    tipo = _map_tipo(raw.get("type") or {})
    ciudad, full_low = _ciudad_de_location(raw.get("location") or {}, ciudades_cfg)

    # Precio de VENTA en USD (operation_type 'Sale'). Si no hay venta, _es_venta=False.
    precio = None
    es_venta = False
    for op in raw.get("operations", []) or []:
        if (op.get("operation_type") or "").lower() == "sale":
            es_venta = True
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
        "ciudad": ciudad,
        "precio_usd": _to_float(precio),
        "superficie_m2": _to_float(raw.get("total_surface") or raw.get("roofed_surface")),
        "dormitorios": _to_int(raw.get("suite_amount") or raw.get("room_amount")),
        "banos": _to_int(raw.get("bathroom_amount")),
        "descripcion": raw.get("description"),
        "link_externo": raw.get("public_url"),
        "_es_venta": es_venta,
        "_full_location": full_low,
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

    ciudades_cfg = _ciudades(cfg)
    ciudades = [c.lower() for c in ciudades_cfg]
    try:
        objetos = _fetch(cfg.api_key)
    except Exception as e:
        resumen = {"ok": False, "motivo": f"Error al consultar Tokko: {e}",
                   "nuevas": 0, "actualizadas": 0}
        cfg.ultima_sync = datetime.utcnow()
        cfg.ultima_sync_resultado = json.dumps(resumen, ensure_ascii=False)
        db.flush()
        return resumen

    nuevas = actualizadas = saltadas = no_venta = 0
    for raw in objetos:
        norm = _normalizar(raw, ciudades_cfg)
        full_loc = norm.pop("_full_location", "")
        es_venta = norm.pop("_es_venta", False)
        # Solo propiedades en venta (módulo Ventas)
        if not es_venta:
            no_venta += 1
            continue
        # Segmentación por ciudad (Mod #7): la ciudad configurada debe aparecer
        # en la jerarquía de ubicación de la propiedad.
        if ciudades and not any(c in full_loc for c in ciudades):
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
               "saltadas_por_ciudad": saltadas, "saltadas_no_venta": no_venta,
               "total_recibidas": len(objetos)}
    cfg.ultima_sync = datetime.utcnow()
    cfg.ultima_sync_resultado = json.dumps(resumen, ensure_ascii=False)
    db.flush()
    return resumen
