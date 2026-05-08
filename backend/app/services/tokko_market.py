"""
Tools del agente IA para analizar la red Tokko.

Estas funciones son SINCRÓNICAS (las llama el dispatcher del agente, que
puede correr fuera del event loop del request). Internamente usan httpx.Client
síncrono.

Endpoints usados:
  GET /property/                — listado simple (cuenta del usuario).
  GET /property/search/         — búsqueda con filtros JSON (alcance: la red
                                  visible para esa key, según permisos
                                  Tokko).
  GET /property/{id}/           — ficha detallada.

Las operaciones Tokko se identifican por id:
  1 = Venta   2 = Alquiler   3 = Alquiler temporal
"""
import json
import os
import statistics as stats
from typing import Optional

import httpx


TOKKO_KEY = os.getenv("TOKKO_API_KEY", "")
TOKKO_URL = os.getenv("TOKKO_API_URL", "https://www.tokkobroker.com/api/v1")

OP_ID = {"venta": 1, "alquiler": 2, "alquiler_temporal": 3}


def _client():
    return httpx.Client(timeout=20.0, verify=False)


def _resumen_propiedad(o: dict) -> dict:
    """Aplana una propiedad de Tokko a un dict liviano."""
    operations = []
    for op in o.get("operations") or []:
        prices = op.get("prices") or []
        precio = prices[0].get("price") if prices else None
        moneda = prices[0].get("currency") if prices else None
        operations.append({
            "tipo": op.get("operation_type"),
            "precio": precio,
            "moneda": moneda,
        })
    loc = o.get("location") or {}
    return {
        "tokko_id": o.get("id"),
        "direccion": o.get("address") or "—",
        "tipo": (o.get("type") or {}).get("name") or "—",
        "ciudad": loc.get("name"),
        "zona": loc.get("full_location"),
        "ambientes": o.get("room_amount"),
        "dormitorios": o.get("suite_amount") or o.get("bedroom_amount"),
        "banos": o.get("bathroom_amount"),
        "superficie_total_m2": o.get("surface_total"),
        "superficie_cubierta_m2": o.get("roofed_surface"),
        "operaciones": operations,
        "expensas": o.get("expenses") or 0,
        "antiguedad": o.get("age"),
        "fotos_url": [(p.get("image") or p.get("original")) for p in (o.get("photos") or [])][:5],
    }


# ────────────────────────────────────────────────────────────────────
# Tool 1: buscar en la red Tokko con filtros
# ────────────────────────────────────────────────────────────────────

def tokko_buscar_red(
    operacion: str = "venta",
    tipo: Optional[str] = None,
    ciudad: Optional[str] = None,
    dormitorios_min: Optional[int] = None,
    precio_min: Optional[float] = None,
    precio_max: Optional[float] = None,
    moneda: str = "USD",
    limit: int = 20,
) -> dict:
    """Busca propiedades en la red de Tokko aplicando filtros."""
    if not TOKKO_KEY:
        return {"ok": False, "error": "TOKKO_API_KEY no configurada"}

    op_id = OP_ID.get((operacion or "venta").lower(), 1)
    # Tokko requiere price_from/price_to siempre presentes; usamos rangos
    # amplios por defecto para "cualquier precio".
    data = {
        "current_localization_id": 0,
        "current_localization_type": "country",
        "operation_types": [op_id],
        "property_types": [],
        "price_from": float(precio_min) if precio_min is not None else 0,
        "price_to": float(precio_max) if precio_max is not None else 999_999_999,
        "currency": (moneda or "USD").upper(),
        "filters": [],
    }
    if dormitorios_min is not None:
        data["filters"].append(["suite_amount", ">=", int(dormitorios_min)])

    params = {
        "key": TOKKO_KEY,
        "format": "json",
        "limit": min(int(limit or 20), 50),
        "lang": "es_ar",
        "data": json.dumps(data),
    }

    with _client() as c:
        r = c.get(f"{TOKKO_URL}/property/search/", params=params)
        if r.status_code != 200:
            return {"ok": False, "http": r.status_code, "error": r.text[:200]}
        body = r.json()

    objs = body.get("objects") or []
    if ciudad:
        ciudad_n = ciudad.lower()
        objs = [
            o for o in objs
            if ciudad_n in ((o.get("location") or {}).get("name", "") or "").lower()
            or ciudad_n in ((o.get("location") or {}).get("full_location", "") or "").lower()
        ]
    if tipo:
        tipo_n = tipo.lower()
        objs = [
            o for o in objs
            if tipo_n in ((o.get("type") or {}).get("name", "") or "").lower()
        ]

    return {
        "ok": True,
        "operacion": operacion,
        "filtros": {"tipo": tipo, "ciudad": ciudad, "dormitorios_min": dormitorios_min,
                    "precio_min": precio_min, "precio_max": precio_max, "moneda": moneda},
        "total_red_sin_filtrar": (body.get("meta") or {}).get("total_count"),
        "total_resultados": len(objs),
        "propiedades": [_resumen_propiedad(o) for o in objs],
    }


# ────────────────────────────────────────────────────────────────────
# Tool 2: ficha detallada de una propiedad de la red
# ────────────────────────────────────────────────────────────────────

def tokko_ficha(tokko_id: int | str) -> dict:
    if not TOKKO_KEY:
        return {"ok": False, "error": "TOKKO_API_KEY no configurada"}
    with _client() as c:
        r = c.get(
            f"{TOKKO_URL}/property/{tokko_id}/",
            params={"key": TOKKO_KEY, "format": "json", "lang": "es_ar"},
        )
        if r.status_code != 200:
            return {"ok": False, "http": r.status_code, "error": r.text[:200]}
        return {"ok": True, "propiedad": _resumen_propiedad(r.json())}


# ────────────────────────────────────────────────────────────────────
# Tool 3: estadísticas de mercado por zona / tipo / operación
# ────────────────────────────────────────────────────────────────────

def tokko_estadisticas_zona(
    operacion: str = "venta",
    tipo: Optional[str] = None,
    ciudad: Optional[str] = None,
    moneda: str = "USD",
    sample: int = 50,
) -> dict:
    """
    Promedio / mediana / min / max de precios y m² para una combinación
    operación+tipo+ciudad. Útil para comparables.
    """
    out = tokko_buscar_red(
        operacion=operacion, tipo=tipo, ciudad=ciudad, moneda=moneda, limit=sample,
    )
    if not out.get("ok"):
        return out
    props = out["propiedades"]
    precios = []
    sup_total = []
    precios_m2 = []
    for p in props:
        # encontrar precio de la operación pedida
        op_target = next(
            (op for op in p["operaciones"] if (op["tipo"] or "").lower() == operacion.lower()),
            None,
        )
        if not op_target or not op_target.get("precio"):
            continue
        precio = float(op_target["precio"])
        precios.append(precio)
        st = p.get("superficie_total_m2")
        if st:
            sup_total.append(float(st))
            if precio:
                precios_m2.append(precio / float(st))

    def _stats(arr: list[float]) -> dict:
        if not arr:
            return {"count": 0}
        return {
            "count": len(arr),
            "min": round(min(arr), 2),
            "max": round(max(arr), 2),
            "promedio": round(stats.mean(arr), 2),
            "mediana": round(stats.median(arr), 2),
        }

    return {
        "ok": True,
        "operacion": operacion,
        "tipo": tipo,
        "ciudad": ciudad,
        "moneda": moneda,
        "muestra_total": len(props),
        "precio": _stats(precios),
        "superficie_total_m2": _stats(sup_total),
        "precio_por_m2": _stats(precios_m2),
    }


# ────────────────────────────────────────────────────────────────────
# Tool 4: comparables a una propiedad local
# ────────────────────────────────────────────────────────────────────

def tokko_comparables(
    db,                    # session SQLAlchemy
    propiedad_id: int,
    operacion: str = "venta",
    tolerancia_m2: int = 30,
) -> dict:
    """
    Dada una propiedad local, busca propiedades comparables en la red
    Tokko (mismo tipo, ciudad similar, ±tolerancia_m2 metros).
    """
    from app import models  # import aquí para evitar ciclos

    p = db.query(models.Propiedad).filter_by(id=propiedad_id).first()
    if not p:
        return {"ok": False, "error": f"Propiedad #{propiedad_id} no encontrada"}

    tipo_str = p.tipo.value if hasattr(p.tipo, "value") else str(p.tipo)
    out = tokko_buscar_red(
        operacion=operacion,
        tipo=tipo_str,
        ciudad=p.ciudad,
        limit=30,
    )
    if not out.get("ok"):
        return out

    sup = float(p.superficie_m2 or 0)
    similares = []
    for r in out["propiedades"]:
        rs = r.get("superficie_total_m2") or 0
        if sup and rs and abs(float(rs) - sup) <= tolerancia_m2:
            similares.append(r)
    if not similares:  # si no hay con tolerancia, devolver los del filtro general
        similares = out["propiedades"][:10]

    # Stats sobre los comparables
    precios = []
    for r in similares:
        op_target = next(
            (op for op in r["operaciones"] if (op["tipo"] or "").lower() == operacion.lower()),
            None,
        )
        if op_target and op_target.get("precio"):
            precios.append(float(op_target["precio"]))

    return {
        "ok": True,
        "propiedad_local": {
            "id": p.id, "direccion": p.direccion, "ciudad": p.ciudad,
            "tipo": tipo_str, "superficie_m2": sup,
            "precio_venta_actual": p.precio_venta or 0,
        },
        "comparables_encontrados": len(similares),
        "precio_promedio": round(stats.mean(precios), 2) if precios else None,
        "precio_mediana": round(stats.median(precios), 2) if precios else None,
        "precio_min": round(min(precios), 2) if precios else None,
        "precio_max": round(max(precios), 2) if precios else None,
        "comparables": similares[:10],
    }
