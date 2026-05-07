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

    contratos_activos = db.query(models.Contrato).filter_by(estado=models.ContratoEstado.vigente).count()
    propiedades_ocupadas = db.query(models.Propiedad).filter_by(estado=models.PropiedadEstado.ocupada).count()
    propiedades_total = db.query(models.Propiedad).count()
    propiedades_disponibles = db.query(models.Propiedad).filter_by(estado=models.PropiedadEstado.disponible).count()

    pagos_mes = db.query(models.Pago).filter(models.Pago.periodo == mes).all()
    cobrado_mes = sum(p.monto_total or 0 for p in pagos_mes if p.estado == models.PagoEstado.pagado)
    pendiente_cobro = sum(p.monto_total or 0 for p in pagos_mes if p.estado == models.PagoEstado.pendiente)
    vencido_mes = sum(p.monto_total or 0 for p in pagos_mes if p.estado == models.PagoEstado.vencido)
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
