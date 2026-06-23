"""Agente IA dentro de la plataforma — asistente conversacional real.

`POST /api/agente/asistente` (y su alias `/consultar`) responden con Claude +
tool-calling, consultando los datos reales del sistema. Lo que el asistente
puede informar **depende del rol** del usuario logueado (ver agente_plataforma).
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models
from app.services import agente_plataforma

router = APIRouter(prefix="/api/agente", tags=["agente"])


class ConsultaIn(BaseModel):
    mensaje: str
    telefono: str | None = None


@router.post("/asistente")
def asistente(data: ConsultaIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Asistente IA de la plataforma. Responde según el rol del usuario."""
    role = getattr(user, "role", "") or ""
    nombre = getattr(user, "nombre", "") or ""
    respuesta = agente_plataforma.responder(data.mensaje, db, role=role, nombre=nombre)

    # Log para auditoría (reusa la tabla de consultas IA).
    try:
        log = models.ConsultaIA(
            telefono=data.telefono, input_text=data.mensaje,
            intent="asistente_plataforma", respuesta=respuesta, user_id=user.id,
        )
        db.add(log); db.commit()
    except Exception:
        db.rollback()

    return {"intent": "asistente_plataforma", "respuesta": respuesta}


# Alias de compatibilidad con el endpoint viejo.
@router.post("/consultar")
def consultar(data: ConsultaIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return asistente(data, db, user)


@router.get("/historial")
def historial(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(models.ConsultaIA).order_by(models.ConsultaIA.id.desc()).limit(50).all()
    return [
        {
            "id": r.id, "telefono": r.telefono, "input": r.input_text,
            "intent": r.intent, "respuesta": r.respuesta,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
