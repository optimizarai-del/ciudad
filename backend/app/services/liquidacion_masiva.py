"""
Liquidaciones masivas mensuales a propietarios.

Para un período YYYY-MM:
  - Toma todos los Pago.estado == pagado del período.
  - Agrupa por propietario (vía propiedad → contrato → propietario).
  - Por cada propietario calcula:
        cobrado_total  = suma de monto_total de sus pagos del período
        comision_total = suma(monto_alquiler * comision_porc / 100) por contrato
        neto_total     = cobrado_total − comision_total ¿ESTO ES INCORRECTO?
                         No. La regla del proyecto: el neto al propietario es
                         alquiler − comisión; las expensas/tasas son pasantes.
                         Entonces neto_propietario_lote =
                            sum( pago.monto_alquiler − comision_de_ese_pago ).
  - Genera un PDF consolidado por propietario.
"""
from datetime import date, datetime
from typing import Optional
from collections import defaultdict
from sqlalchemy.orm import Session

from app import models


def _nombre_cliente(c: models.Cliente | None) -> str:
    if not c:
        return "—"
    if c.razon_social:
        return c.razon_social
    return " ".join(p for p in [c.nombre, c.apellido] if p) or "—"


def calcular_lote(db: Session, periodo: str) -> dict:
    """
    Devuelve el resumen para preview ANTES de generar PDFs.

    {
      "periodo": "2026-05",
      "total_propietarios": 4,
      "monto_cobrado_total": 1_234_567,
      "comision_total": 61_728,
      "neto_total_propietarios": 1_172_839,
      "propietarios": [
        {
          "propietario_id": 1,
          "nombre": "Maria Gonzalez",
          "email": "...",
          "items": [
            {"contrato_id": 5, "propiedad": "Av. ...", "alquiler": 350000,
             "expensas": 50000, "tasas": 17000, "otros": 0,
             "comision_porc": 5, "comision": 17500, "neto_alquiler": 332500},
            ...
          ],
          "totales": {"alquiler": ..., "comision": ..., "neto": ...,
                      "expensas": ..., "tasas": ..., "otros": ...,
                      "cobrado_total": ...}
        }, ...
      ]
    }
    """
    pagos = (
        db.query(models.Pago)
        .filter(models.Pago.periodo == periodo, models.Pago.estado == models.PagoEstado.pagado)
        .all()
    )

    grupos: dict[int, dict] = defaultdict(lambda: {"items": [], "propietario": None})
    sin_propietario = []

    for p in pagos:
        contrato = p.contrato
        if not contrato:
            continue
        propiedad = contrato.propiedad
        if not propiedad or not propiedad.propietario_id:
            sin_propietario.append({"pago_id": p.id, "contrato": contrato.codigo})
            continue
        propietario = propiedad.propietario
        comision_porc = float(contrato.comision_porc or 0)
        alquiler = float(p.monto_alquiler or 0)
        expensas = float(p.monto_expensas or 0)
        tasas = float((p.monto_municipal or 0) + (p.monto_impuestos or 0))
        otros = float(p.monto_otros or 0)
        comision = round(alquiler * comision_porc / 100.0, 2)
        neto_alquiler = round(alquiler - comision, 2)
        cobrado = float(p.monto_total or 0)

        g = grupos[propietario.id]
        g["propietario"] = propietario
        g["items"].append({
            "pago_id": p.id,
            "contrato_id": contrato.id,
            "contrato_codigo": contrato.codigo,
            "propiedad": propiedad.direccion,
            "propiedad_id": propiedad.id,
            "fecha_pago": p.fecha_pago.isoformat() if p.fecha_pago else None,
            "alquiler": alquiler,
            "expensas": expensas,
            "tasas": tasas,
            "otros": otros,
            "cobrado_total": cobrado,
            "comision_porc": comision_porc,
            "comision": comision,
            "neto_alquiler": neto_alquiler,
        })

    propietarios_out = []
    cobrado_lote = 0.0
    comision_lote = 0.0
    neto_lote = 0.0
    for prop_id, g in grupos.items():
        items = g["items"]
        sub = {
            "alquiler": sum(i["alquiler"] for i in items),
            "expensas": sum(i["expensas"] for i in items),
            "tasas": sum(i["tasas"] for i in items),
            "otros": sum(i["otros"] for i in items),
            "cobrado_total": sum(i["cobrado_total"] for i in items),
            "comision": sum(i["comision"] for i in items),
            "neto": sum(i["neto_alquiler"] for i in items),
        }
        cobrado_lote += sub["cobrado_total"]
        comision_lote += sub["comision"]
        neto_lote += sub["neto"]
        pr = g["propietario"]
        propietarios_out.append({
            "propietario_id": prop_id,
            "nombre": _nombre_cliente(pr),
            "documento": pr.documento,
            "email": pr.email,
            "telefono": pr.telefono,
            "items": items,
            "totales": {k: round(v, 2) for k, v in sub.items()},
        })
    propietarios_out.sort(key=lambda x: x["nombre"])

    return {
        "periodo": periodo,
        "total_propietarios": len(propietarios_out),
        "total_pagos": sum(len(p["items"]) for p in propietarios_out),
        "monto_cobrado_total": round(cobrado_lote, 2),
        "comision_total": round(comision_lote, 2),
        "neto_total_propietarios": round(neto_lote, 2),
        "propietarios": propietarios_out,
        "pagos_sin_propietario": sin_propietario,
    }
