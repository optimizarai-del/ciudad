"""
Tasación automática por comparables (AVM) — Mod #1.

Estrategia:
  1. Buscar propiedades comparables en el catálogo: mismo tipo, mismo barrio
     (si se indica), superficie ±20%, con precio y superficie cargados.
  2. Calcular el valor/m² mediano de esos comparables.
  3. Si no hay comparables suficientes (<3), usar la tabla de referencia
     valor_m2 por barrio+tipo como fallback.
  4. Ajustar por estado de conservación y devolver rango + confianza.

En Fase 2 el pool de comparables se enriquece con propiedades de Tokko.
En Fase 3 se suma el informe narrativo con Claude.
"""
import json
from statistics import median

from sqlalchemy.orm import Session

from app import models_ventas as mv

# Ajuste por estado de conservación sobre el valor base
_AJUSTE_ESTADO = {
    "nuevo": 1.05,
    "bueno": 1.0,
    "a_refaccionar": 0.88,
}


def _comparables(db: Session, *, tipo, barrio_id, superficie_m2):
    q = db.query(mv.VentasPropiedad).filter(
        mv.VentasPropiedad.precio_usd.isnot(None),
        mv.VentasPropiedad.superficie_m2.isnot(None),
        mv.VentasPropiedad.superficie_m2 > 0,
    )
    if tipo:
        q = q.filter(mv.VentasPropiedad.tipo == tipo)
    if barrio_id:
        q = q.filter(mv.VentasPropiedad.barrio_id == barrio_id)

    lo, hi = superficie_m2 * 0.8, superficie_m2 * 1.2
    comps = [
        p for p in q.all()
        if lo <= p.superficie_m2 <= hi
    ]
    return comps


def tasar(db: Session, req) -> dict:
    """req: schemas_ventas.TasacionRequest. Devuelve dict listo para persistir."""
    sup = req.superficie_m2 or 0
    comps = _comparables(db, tipo=req.tipo, barrio_id=req.barrio_id, superficie_m2=sup) if sup else []

    valores_m2 = [p.precio_usd / p.superficie_m2 for p in comps]
    metodo = "comparables"
    comparables_data = [
        {
            "id": p.id,
            "direccion": p.direccion,
            "precio_usd": p.precio_usd,
            "superficie_m2": p.superficie_m2,
            "valor_m2": round(p.precio_usd / p.superficie_m2, 2),
        }
        for p in comps
    ]

    if len(valores_m2) >= 3:
        valor_m2 = median(valores_m2)
        confianza = "alta" if len(valores_m2) >= 5 else "media"
    else:
        # Fallback a tabla de referencia barrio+tipo
        ref = None
        if req.barrio_id:
            ref = (
                db.query(mv.VentasValorM2Referencia)
                .filter(
                    mv.VentasValorM2Referencia.barrio_id == req.barrio_id,
                    mv.VentasValorM2Referencia.tipo == req.tipo,
                )
                .first()
            )
        if ref:
            valor_m2 = ref.valor_m2_usd
            metodo = "referencia"
            confianza = "baja"
        elif valores_m2:
            valor_m2 = median(valores_m2)
            confianza = "baja"
        else:
            # Sin datos: no se puede tasar
            return {
                "tipo": req.tipo,
                "barrio_id": req.barrio_id,
                "direccion": req.direccion,
                "superficie_m2": sup,
                "valor_m2_usado": None,
                "valor_min_usd": None,
                "valor_medio_usd": None,
                "valor_max_usd": None,
                "confianza": "sin_datos",
                "metodo": "sin_datos",
                "comparables_json": json.dumps([]),
            }

    ajuste = _AJUSTE_ESTADO.get(req.estado_conservacion or "bueno", 1.0)
    valor_medio = valor_m2 * sup * ajuste

    return {
        "tipo": req.tipo,
        "barrio_id": req.barrio_id,
        "direccion": req.direccion,
        "superficie_m2": sup,
        "dormitorios": req.dormitorios,
        "banos": req.banos,
        "antiguedad_anios": req.antiguedad_anios,
        "estado_conservacion": req.estado_conservacion,
        "valor_m2_usado": round(valor_m2, 2),
        "valor_min_usd": round(valor_medio * 0.92, 0),
        "valor_medio_usd": round(valor_medio, 0),
        "valor_max_usd": round(valor_medio * 1.08, 0),
        "confianza": confianza,
        "metodo": metodo,
        "comparables_json": json.dumps(comparables_data, ensure_ascii=False),
    }
