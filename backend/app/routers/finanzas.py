"""
Dashboard financiero histórico.

  GET /api/finanzas/historico?meses=12  — cobrado/pendiente/vencido por mes
  GET /api/finanzas/mora                — mora actual (vencidos sin pagar)
  GET /api/finanzas/proyeccion          — proyección de cobro de los próx 3 meses
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.security import get_current_user
from app import models


router = APIRouter(prefix="/api/finanzas", tags=["finanzas"])


def _periodos_meses(n: int) -> list[str]:
    hoy = date.today()
    out = []
    y, m = hoy.year, hoy.month
    for _ in range(n):
        out.append(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            y -= 1
            m = 12
    return list(reversed(out))


@router.get("/historico")
def historico(meses: int = 12, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    Devuelve [{mes, cobrado, pendiente, vencido, contratos_activos}] de los
    últimos `meses` meses (incluye el actual).
    """
    meses = max(1, min(int(meses), 24))
    periodos = _periodos_meses(meses)

    # Pagos por período
    pagos_por_periodo = {}
    for p in db.query(models.Pago).filter(models.Pago.periodo.in_(periodos)).all():
        pagos_por_periodo.setdefault(p.periodo, []).append(p)

    # Contratos activos al cierre de cada mes (los que tenían fecha_inicio<=fin_mes
    # y (fecha_fin >= inicio_mes o fecha_fin null) y estado vigente).
    contratos = db.query(models.Contrato).all()

    out = []
    for per in periodos:
        y, m = map(int, per.split("-"))
        # último día del mes
        if m == 12:
            fin = date(y, 12, 31)
        else:
            fin = date(y, m + 1, 1) - timedelta(days=1)
        ini = date(y, m, 1)

        cobrado = 0.0
        pendiente = 0.0
        vencido = 0.0
        for p in pagos_por_periodo.get(per, []):
            est = p.estado.value if hasattr(p.estado, "value") else p.estado
            mt = p.monto_total or 0
            if est == "pagado":
                cobrado += mt
            elif est == "vencido":
                vencido += mt
            else:
                pendiente += mt

        # contratos vigentes en el mes: aproximación
        activos = sum(
            1 for c in contratos
            if (c.estado.value if hasattr(c.estado, "value") else c.estado) == "vigente"
            and (not c.fecha_inicio or c.fecha_inicio <= fin)
            and (not c.fecha_fin or c.fecha_fin >= ini)
        )

        out.append({
            "mes": per,
            "cobrado": round(cobrado, 2),
            "pendiente": round(pendiente, 2),
            "vencido": round(vencido, 2),
            "total_esperado": round(cobrado + pendiente + vencido, 2),
            "porcentaje_cobrado": round(
                (cobrado / (cobrado + pendiente + vencido) * 100) if (cobrado + pendiente + vencido) > 0 else 0, 1
            ),
            "contratos_activos": activos,
            "pagos_count": len(pagos_por_periodo.get(per, [])),
        })

    return {"meses": meses, "data": out}


@router.get("/mora")
def mora(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Pagos vencidos sin saldar — situación de mora actual."""
    hoy = date.today()
    items = []
    monto_total = 0.0

    pagos = (
        db.query(models.Pago)
        .filter(or_(
            models.Pago.estado == models.PagoEstado.vencido,
            models.Pago.estado == models.PagoEstado.pendiente,
        ))
        .all()
    )
    for p in pagos:
        if p.estado == models.PagoEstado.pagado:
            continue
        # Mora = vencido OR pendiente con vencimiento pasado
        es_mora = p.estado == models.PagoEstado.vencido
        if not es_mora and p.fecha_vencimiento and p.fecha_vencimiento < hoy:
            es_mora = True
        if not es_mora:
            continue

        c = p.contrato
        prop = c.propiedad if c else None
        inq = c.inquilino if c else None
        dias = (hoy - p.fecha_vencimiento).days if p.fecha_vencimiento else 0
        monto = p.monto_total or 0
        monto_total += monto
        items.append({
            "pago_id": p.id,
            "contrato_id": c.id if c else None,
            "contrato_codigo": c.codigo if c else None,
            "propiedad": prop.direccion if prop else "—",
            "inquilino": " ".join([x for x in [inq.nombre, inq.apellido] if x]) if inq else "—",
            "inquilino_email": inq.email if inq else None,
            "periodo": p.periodo,
            "monto": monto,
            "fecha_vencimiento": p.fecha_vencimiento.isoformat() if p.fecha_vencimiento else None,
            "dias_atraso": max(0, dias),
        })
    items.sort(key=lambda x: x["dias_atraso"], reverse=True)
    return {
        "total_items": len(items),
        "monto_total": round(monto_total, 2),
        "items": items,
    }


@router.get("/proyeccion")
def proyeccion(meses: int = 3, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    Proyección de cobro: para cada mes futuro, estima el ingreso esperado
    en base al precio_alquiler de los contratos vigentes (sin ajustes).
    """
    meses = max(1, min(int(meses), 12))
    hoy = date.today()
    contratos = db.query(models.Contrato).filter(
        models.Contrato.estado == models.ContratoEstado.vigente
    ).all()

    out = []
    for off in range(1, meses + 1):
        y = hoy.year
        m = hoy.month + off
        while m > 12:
            m -= 12
            y += 1
        per = f"{y}-{m:02d}"
        primer = date(y, m, 1)
        ultimo = date(y, 12, 31) if m == 12 else date(y, m + 1, 1) - timedelta(days=1)

        total = 0.0
        n_contratos = 0
        for c in contratos:
            # Sólo si el contrato sigue vigente en ese mes
            if c.fecha_fin and c.fecha_fin < primer:
                continue
            if c.fecha_inicio and c.fecha_inicio > ultimo:
                continue
            base = float(c.monto_inicial or 0)
            prop = c.propiedad
            extras = (prop.expensas if prop else 0) + (prop.tasa_municipal if prop else 0)
            total += base + (extras or 0)
            n_contratos += 1
        out.append({"mes": per, "esperado": round(total, 2), "contratos": n_contratos})
    return {"meses": meses, "data": out}
