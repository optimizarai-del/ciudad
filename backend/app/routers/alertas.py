from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models

router = APIRouter(prefix="/api/alertas", tags=["alertas"])


@router.get("/vencimientos")
def vencimientos(dias: int = 60, db: Session = Depends(get_db), user=Depends(get_current_user)):
    hoy = date.today()
    limite = hoy + timedelta(days=dias)

    contratos = (
        db.query(models.Contrato)
        .filter(
            models.Contrato.estado == models.ContratoEstado.vigente,
            models.Contrato.fecha_fin.isnot(None),
            models.Contrato.fecha_fin <= limite,
            models.Contrato.fecha_fin >= hoy,
        )
        .order_by(models.Contrato.fecha_fin)
        .all()
    )

    resultado = []
    for c in contratos:
        dias_restantes = (c.fecha_fin - hoy).days
        if dias_restantes <= 7:
            urgencia = "critico"
        elif dias_restantes <= 30:
            urgencia = "pronto"
        else:
            urgencia = "normal"

        prop = db.query(models.Propiedad).filter_by(id=c.propiedad_id).first()
        inquilino = db.query(models.Cliente).filter_by(id=c.inquilino_id).first() if c.inquilino_id else None

        resultado.append({
            "id": c.id,
            "codigo": c.codigo or f"#{c.id}",
            "tipo": c.tipo,
            "propiedad": prop.direccion if prop else f"Propiedad #{c.propiedad_id}",
            "inquilino": f"{inquilino.nombre} {inquilino.apellido or ''}".strip() if inquilino else None,
            "fecha_fin": c.fecha_fin.isoformat(),
            "dias_restantes": dias_restantes,
            "urgencia": urgencia,
        })

    return resultado
