"""Endpoints del Historial de Acciones (audit + undo).

GET  /api/historial                  — listado paginado con filtros
GET  /api/historial/{id}             — detalle con snapshots
POST /api/historial/{id}/revertir    — deshacer la acción
"""
import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models, schemas
from app.services import historial as historial_service

router = APIRouter(prefix="/api/historial", tags=["historial"])


def _row_to_out(row: models.AccionHistorial) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at,
        "user_id": row.user_id,
        "user_nombre": row.user_nombre,
        "entidad": row.entidad,
        "entidad_id": row.entidad_id,
        "accion": row.accion.value if hasattr(row.accion, "value") else row.accion,
        "descripcion": row.descripcion,
        "revertible": row.revertible,
        "revertida": row.revertida,
        "revertida_at": row.revertida_at,
        "revertida_by_id": row.revertida_by_id,
        "revertida_motivo": row.revertida_motivo,
    }


@router.get("")
def listar(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    entidad: Optional[str] = None,
    entidad_id: Optional[int] = None,
    accion: Optional[str] = None,
    user_id: Optional[int] = None,
    solo_revertibles: bool = False,
    incluir_revertidas: bool = True,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Listado paginado de acciones, más recientes primero.

    Permisos: cualquier usuario autenticado ve el historial. La UI
    decide si filtra por sí mismo o muestra el de todos según el rol.
    """
    q = db.query(models.AccionHistorial).order_by(models.AccionHistorial.created_at.desc())
    if entidad:
        q = q.filter(models.AccionHistorial.entidad == entidad)
    if entidad_id is not None:
        q = q.filter(models.AccionHistorial.entidad_id == entidad_id)
    if accion:
        q = q.filter(models.AccionHistorial.accion == accion)
    if user_id is not None:
        q = q.filter(models.AccionHistorial.user_id == user_id)
    if solo_revertibles:
        q = q.filter(models.AccionHistorial.revertible == True,  # noqa: E712
                     models.AccionHistorial.revertida == False)  # noqa: E712
    if not incluir_revertidas:
        q = q.filter(models.AccionHistorial.revertida == False)  # noqa: E712

    total = q.count()
    rows = q.offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_row_to_out(r) for r in rows],
    }


@router.get("/{accion_id}")
def detalle(
    accion_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    row = db.query(models.AccionHistorial).get(accion_id)
    if not row:
        raise HTTPException(404, "Acción no encontrada")
    out = _row_to_out(row)
    out["snapshot_antes"] = json.loads(row.snapshot_antes) if row.snapshot_antes else None
    out["snapshot_despues"] = json.loads(row.snapshot_despues) if row.snapshot_despues else None
    return out


@router.post("/{accion_id}/revertir")
def revertir(
    accion_id: int,
    payload: Optional[schemas.RevertirAccionIn] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Deshace la acción. Si falla, hace rollback y devuelve 400 con el motivo."""
    motivo = payload.motivo if payload else None
    try:
        row = historial_service.revertir(db, accion_id, user, motivo=motivo)
        db.commit()
        return {
            "ok": True,
            "accion_id": row.id,
            "revertida_at": row.revertida_at.isoformat() if row.revertida_at else None,
        }
    except historial_service.RevertError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        print(f"[historial.revertir] {type(e).__name__}: {e}")
        raise HTTPException(500, f"Error al revertir: {type(e).__name__}")
