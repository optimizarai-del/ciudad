"""
Caja — flujo de dinero de la inmobiliaria por período.

Mirada simple de "cuánto entró, cuánto salió y cuánto ganamos" en un rango:
  - **Ingresos**: lo cobrado a los inquilinos (pagos), por `fecha_pago`.
  - **Egresos**: lo entregado a los propietarios (liquidaciones), por
    `fecha_liquidacion_propietario`.
  - **Comisiones**: la ganancia de la inmobiliaria = alquiler × comisión%.
  - **Saldo de caja**: ingresos − egresos (plata que entró y todavía no se
    entregó al propietario).

GET /api/caja?rango=diaria|semanal|mensual|anual&fecha=YYYY-MM-DD
"""
from datetime import date, timedelta
from calendar import monthrange
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.security import get_current_user
from app import models
from app.services.workspace import apply_workspace_filter as _ws

router = APIRouter(prefix="/api/caja", tags=["caja"])


def _ventana(rango: str, ref: date) -> tuple[date, date, str]:
    """Devuelve (desde, hasta, etiqueta) para el rango pedido centrado en `ref`."""
    r = (rango or "mensual").lower()
    if r in ("diaria", "diario", "dia"):
        return ref, ref, ref.strftime("%d/%m/%Y")
    if r in ("semanal", "semana"):
        desde = ref - timedelta(days=ref.weekday())      # lunes
        hasta = desde + timedelta(days=6)                # domingo
        return desde, hasta, f"Semana del {desde.strftime('%d/%m')} al {hasta.strftime('%d/%m/%Y')}"
    if r in ("anual", "ano", "año", "anio"):
        return date(ref.year, 1, 1), date(ref.year, 12, 31), str(ref.year)
    # default: mensual
    desde = date(ref.year, ref.month, 1)
    hasta = date(ref.year, ref.month, monthrange(ref.year, ref.month)[1])
    meses = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    return desde, hasta, f"{meses[ref.month].capitalize()} {ref.year}"


@router.get("")
def caja(rango: str = "mensual", fecha: Optional[str] = None,
         db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        ref = date.fromisoformat(fecha) if fecha else date.today()
    except ValueError:
        raise HTTPException(400, "Fecha inválida (usar YYYY-MM-DD)")

    desde, hasta, etiqueta = _ventana(rango, ref)

    # ── INGRESOS: pagos cobrados en la ventana (por fecha_pago) ──────────────
    pagos = (
        _ws(db.query(models.Pago), models.Pago, user)
        .options(joinedload(models.Pago.contrato))
        .filter(models.Pago.estado == models.PagoEstado.pagado)
        .filter(models.Pago.fecha_pago.isnot(None))
        .filter(models.Pago.fecha_pago >= desde, models.Pago.fecha_pago <= hasta)
        .all()
    )
    ing = {"total": 0.0, "alquiler": 0.0, "expensas": 0.0, "municipal": 0.0,
           "otros": 0.0, "cantidad": len(pagos)}
    comisiones = 0.0
    for p in pagos:
        ing["total"] += float(p.monto_total or 0)
        ing["alquiler"] += float(p.monto_alquiler or 0)
        ing["expensas"] += float(p.monto_expensas or 0)
        ing["municipal"] += float(p.monto_municipal or 0)
        ing["otros"] += float(p.monto_otros or 0)
        porc = float(p.contrato.comision_porc or 0) if p.contrato else 0.0
        comisiones += float(p.monto_alquiler or 0) * porc / 100.0

    # ── EGRESOS: liquidaciones entregadas en la ventana ──────────────────────
    liqs = (
        _ws(db.query(models.Pago), models.Pago, user)
        .filter(models.Pago.liquidado_propietario.is_(True))
        .filter(models.Pago.fecha_liquidacion_propietario.isnot(None))
        .filter(models.Pago.fecha_liquidacion_propietario >= desde,
                models.Pago.fecha_liquidacion_propietario <= hasta)
        .all()
    )
    egr_total = sum(float(p.monto_liquidado_propietario or 0) for p in liqs)

    return {
        "rango": (rango or "mensual").lower(),
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "etiqueta": etiqueta,
        "ingresos": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in ing.items()},
        "egresos": {"total": round(egr_total, 2), "cantidad": len(liqs)},
        "comisiones": round(comisiones, 2),
        "ganancia": round(comisiones, 2),               # ganancia de la inmobiliaria
        "saldo_caja": round(ing["total"] - egr_total, 2),  # entró − entregado
    }
