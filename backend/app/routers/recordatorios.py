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
from app.services.workspace import apply_workspace_filter as _ws, is_demo_user


router = APIRouter(prefix="/api/recordatorios", tags=["recordatorios"])


@router.post("/run")
async def run_now(user=Depends(get_current_user)):
    """Corre un ciclo de chequeos ahora mismo. Útil para testear."""
    out = await rsvc.correr_un_ciclo()
    return out


def _eventos_visibles(
    db: Session,
    user,
    es_critico: Optional[bool] = None,
    tipo: Optional[str] = None,
    limit: int = 100,
):
    """Devuelve los eventos visibles para el workspace del usuario.

    Filtro: el evento se incluye si su contrato_id pertenece a un contrato
    del workspace del usuario, o si no tiene contrato_id (evento global)
    y el usuario es del workspace real.
    """
    ids_contratos_ws = {c.id for c in
        _ws(db.query(models.Contrato), models.Contrato, user).all()
    }
    q = db.query(models.Evento).order_by(models.Evento.created_at.desc())
    if es_critico is not None:
        q = q.filter(models.Evento.es_critico == es_critico)
    if tipo:
        q = q.filter(models.Evento.tipo == tipo)
    # Recorrer y filtrar por workspace. Cap a 2x el limit para no traer todo.
    raw = q.limit(max(limit * 2, 50)).all()
    out = []
    es_demo = is_demo_user(user)
    for e in raw:
        if e.contrato_id and e.contrato_id not in ids_contratos_ws:
            continue
        if not e.contrato_id and es_demo:
            continue
        out.append(e)
        if len(out) >= limit:
            break
    return out


@router.get("/eventos")
def listar_eventos(
    limit: int = Query(50, ge=1, le=200),
    es_critico: Optional[bool] = None,
    tipo: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        rows = _eventos_visibles(db, user, es_critico=es_critico, tipo=tipo, limit=limit)
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
    except Exception as e:
        print(f"[recordatorios.listar_eventos] {type(e).__name__}: {e}")
        return []


@router.get("/resumen")
def resumen(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Stats rápidos para mostrar arriba de la página de Recordatorios."""
    rows = _eventos_visibles(db, user, limit=500)
    return {
        "total": len(rows),
        "criticos": sum(1 for e in rows if e.es_critico),
        "ultimo": rows[0].created_at.isoformat() if rows else None,
    }
