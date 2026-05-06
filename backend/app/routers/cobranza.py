"""
GET  /api/cobranza/mensual?mes=2026-05   → todos los pagos del mes con estado
PATCH /api/cobranza/{pago_id}/cobrar     → marcar cobrado en un clic
GET  /api/cobranza/resumen?mes=2026-05  → totales cobrado/pendiente/vencido
"""
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app import models

router = APIRouter(prefix="/api/cobranza", tags=["cobranza"])

@router.get("/mensual")
def cobranza_mensual(mes: Optional[str] = None, db: Session = Depends(get_db)):
    """Devuelve todos los pagos del mes con info de propiedad e inquilino."""
    if not mes:
        hoy = date.today()
        mes = f"{hoy.year}-{hoy.month:02d}"

    year, month = map(int, mes.split("-"))

    pagos = db.query(models.Pago).filter(
        models.Pago.periodo == mes
    ).all()

    # If no pagos for this period, get all pending from active contracts
    if not pagos:
        contratos = db.query(models.Contrato).filter(
            models.Contrato.estado == models.ContratoEstado.vigente
        ).all()
        # Return contract-based view
        result = []
        for c in contratos:
            prop = c.propiedad
            inq = c.inquilino
            result.append({
                "pago_id": None,
                "contrato_id": c.id,
                "contrato_codigo": c.codigo,
                "propiedad": prop.direccion if prop else "",
                "propiedad_ciudad": prop.ciudad if prop else "",
                "inquilino": f"{inq.nombre} {inq.apellido or ''}".strip() if inq else "Sin inquilino",
                "inquilino_telefono": inq.telefono if inq else "",
                "monto_total": c.monto_inicial,
                "fecha_vencimiento": None,
                "fecha_pago": None,
                "estado": "sin_pago",
                "periodo": mes,
            })
        return result

    result = []
    for p in pagos:
        c = p.contrato
        prop = c.propiedad if c else None
        inq = c.inquilino if c else None
        result.append({
            "pago_id": p.id,
            "contrato_id": c.id if c else None,
            "contrato_codigo": c.codigo if c else "",
            "propiedad": prop.direccion if prop else "",
            "propiedad_ciudad": prop.ciudad if prop else "",
            "inquilino": f"{inq.nombre} {inq.apellido or ''}".strip() if inq else "",
            "inquilino_telefono": inq.telefono if inq else "",
            "monto_total": p.monto_total,
            "fecha_vencimiento": p.fecha_vencimiento.isoformat() if p.fecha_vencimiento else None,
            "fecha_pago": p.fecha_pago.isoformat() if p.fecha_pago else None,
            "estado": p.estado,
            "periodo": p.periodo,
        })
    return result


@router.patch("/{pago_id}/cobrar")
def marcar_cobrado(pago_id: int, db: Session = Depends(get_db)):
    pago = db.query(models.Pago).get(pago_id)
    if not pago:
        raise HTTPException(404, "Pago no encontrado")
    pago.estado = models.PagoEstado.pagado
    pago.fecha_pago = date.today()
    db.commit()
    return {"ok": True, "fecha_pago": pago.fecha_pago.isoformat()}


@router.get("/resumen")
def resumen_cobranza(mes: Optional[str] = None, db: Session = Depends(get_db)):
    if not mes:
        hoy = date.today()
        mes = f"{hoy.year}-{hoy.month:02d}"

    pagos = db.query(models.Pago).filter(models.Pago.periodo == mes).all()

    cobrado = sum(p.monto_total for p in pagos if p.estado == models.PagoEstado.pagado)
    pendiente = sum(p.monto_total for p in pagos if p.estado == models.PagoEstado.pendiente)
    vencido = sum(p.monto_total for p in pagos if p.estado == models.PagoEstado.vencido)
    total = cobrado + pendiente + vencido

    contratos_activos = db.query(models.Contrato).filter(
        models.Contrato.estado == models.ContratoEstado.vigente
    ).count()

    return {
        "mes": mes,
        "cobrado": cobrado,
        "pendiente": pendiente,
        "vencido": vencido,
        "total_esperado": total,
        "porcentaje_cobrado": round((cobrado / total * 100) if total > 0 else 0, 1),
        "contratos_activos": contratos_activos,
        "pagos_count": len(pagos),
    }
