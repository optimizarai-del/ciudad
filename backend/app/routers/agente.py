"""Agente IA — placeholder para Fase 3.
Endpoints stub que devuelven respuestas simuladas.
En Fase 3 se conecta a webhook WhatsApp + LLM con tool-calling.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models

router = APIRouter(prefix="/api/agente", tags=["agente"])


class ConsultaIn(BaseModel):
    mensaje: str
    telefono: str | None = None


@router.post("/consultar")
def consultar(data: ConsultaIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # Stub demo — busca por palabras clave
    msg = data.mensaje.lower()
    intent = "desconocido"
    respuesta = "No entendí la consulta. Probá: 'cuántas propiedades tengo' o 'calculá alquiler de [dirección]'."

    if "cuanta" in msg or "cuántas" in msg or "total" in msg:
        n = db.query(models.Propiedad).count()
        intent = "contar_propiedades"
        respuesta = f"Tenés {n} propiedades cargadas en el sistema."
    elif "calcul" in msg or "alquiler" in msg:
        intent = "calcular_alquiler"
        respuesta = "Para calcular usá la calculadora con la dirección. (En Fase 3 lo hago directamente acá)."
    elif "contrato" in msg:
        n = db.query(models.Contrato).filter_by(estado=models.ContratoEstado.vigente).count()
        intent = "contar_contratos"
        respuesta = f"Hay {n} contratos vigentes."

    log = models.ConsultaIA(
        telefono=data.telefono,
        input_text=data.mensaje,
        intent=intent,
        respuesta=respuesta,
        user_id=user.id,
    )
    db.add(log); db.commit()
    return {"intent": intent, "respuesta": respuesta}


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
