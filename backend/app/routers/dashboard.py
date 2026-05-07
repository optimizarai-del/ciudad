from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/hud")
def hud(db: Session = Depends(get_db), user=Depends(get_current_user)):
    total_props = db.query(models.Propiedad).count()
    disponibles = db.query(models.Propiedad).filter_by(estado=models.PropiedadEstado.disponible).count()
    ocupadas = db.query(models.Propiedad).filter_by(estado=models.PropiedadEstado.ocupada).count()
    contratos_vigentes = db.query(models.Contrato).filter_by(estado=models.ContratoEstado.vigente).count()
    clientes = db.query(models.Cliente).count()
    return {
        "propiedades_total": total_props,
        "propiedades_disponibles": disponibles,
        "propiedades_ocupadas": ocupadas,
        "contratos_vigentes": contratos_vigentes,
        "clientes_total": clientes,
    }


@router.get("/stats")
def stats(mes: Optional[str] = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    KPIs para el dashboard de alquileres.
    `mes` formato YYYY-MM; default: mes actual.
    """
    if not mes:
        hoy = date.today()
        mes = f"{hoy.year}-{hoy.month:02d}"

    propiedades_ocupadas = db.query(models.Propiedad).filter_by(estado=models.PropiedadEstado.ocupada).count()
    propiedades_total = db.query(models.Propiedad).count()
    propiedades_disponibles = db.query(models.Propiedad).filter_by(estado=models.PropiedadEstado.disponible).count()

    contratos = db.query(models.Contrato).filter_by(estado=models.ContratoEstado.vigente).all()
    contratos_activos = len(contratos)

    cobrado_mes = pendiente_cobro = vencido_mes = 0.0
    for c in contratos:
        pago = (
            db.query(models.Pago)
            .filter(models.Pago.contrato_id == c.id, models.Pago.periodo == mes)
            .order_by(models.Pago.id.desc())
            .first()
        )
        if pago:
            monto = pago.monto_total or 0
            if pago.estado == models.PagoEstado.pagado:
                cobrado_mes += monto
            elif pago.estado == models.PagoEstado.vencido:
                vencido_mes += monto
            else:
                pendiente_cobro += monto
        else:
            prop = c.propiedad
            base = float(c.monto_inicial or (prop.precio_alquiler if prop else 0) or 0)
            tasas = (prop.tasa_municipal if prop else 0) + (prop.impuesto_inmobiliario if prop else 0)
            extras = (prop.expensas if prop else 0) + (tasas or 0)
            pendiente_cobro += round(base + (extras or 0), 2)

    total_esperado = cobrado_mes + pendiente_cobro + vencido_mes

    return {
        "mes": mes,
        # campos solicitados por QA
        "contratos_activos": contratos_activos,
        "propiedades_ocupadas": propiedades_ocupadas,
        "cobrado_mes": cobrado_mes,
        "pendiente_cobro": pendiente_cobro,
        # alias usados por el frontend actual
        "contratos_vigentes": contratos_activos,
        "propiedades_total": propiedades_total,
        "propiedades_disponibles": propiedades_disponibles,
        "vencido_mes": vencido_mes,
        "total_esperado": total_esperado,
        "porcentaje_cobrado": round((cobrado_mes / total_esperado * 100) if total_esperado > 0 else 0, 1),
    }
