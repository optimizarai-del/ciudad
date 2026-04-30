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
