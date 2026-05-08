"""
Recordatorios:
  POST /api/recordatorios/run     — corre un ciclo on-demand (panel admin).
  GET  /api/recordatorios/status  — última corrida + qué se generó.
  GET  /api/recordatorios/eventos — lista de eventos del activity log.
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models
from app.services import recordatorios as rsvc


router = APIRouter(prefix="/api/recordatorios", tags=["recordatorios"])


@router.post("/run")
async def run_now(user=Depends(get_current_user)):
    """Corre un ciclo de chequeos ahora mismo. Útil para testear."""
    out = await rsvc.correr_un_ciclo()
    return out


@router.get("/eventos")
def listar_eventos(
    limit: int = Query(50, ge=1, le=200),
    es_critico: Optional[bool] = None,
    tipo: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    q = db.query(models.Evento).order_by(models.Evento.created_at.desc())
    if es_critico is not None:
        q = q.filter(models.Evento.es_critico == es_critico)
    if tipo:
        q = q.filter(models.Evento.tipo == tipo)
    rows = q.limit(limit).all()
    return [{
        "id": e.id,
        "tipo": e.tipo.value if hasattr(e.tipo, "value") else e.tipo,
        "titulo": e.titulo,
        "descripcion": e.descripcion,
        "es_critico": e.es_critico,
        "contrato_id": e.contrato_id,
        "propiedad_id": e.propiedad_id,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    } for e in rows]
