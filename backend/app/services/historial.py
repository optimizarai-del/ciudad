"""Servicio de historial de acciones + reversión (undo).

Uso típico desde un router:

    from app.services import historial

    # Antes de modificar
    snapshot_antes = historial.snapshot(pago)

    pago.estado = models.PagoEstado.pagado
    pago.fecha_pago = date.today()
    db.commit()

    historial.registrar(
        db, user,
        entidad="pagos",
        entidad_id=pago.id,
        accion=models.AccionTipo.cobrar,
        descripcion=f"Marcó pago #{pago.id} ({pago.periodo}) como cobrado",
        antes=snapshot_antes,
        despues=historial.snapshot(pago),
    )

Para revertir:

    historial.revertir(db, accion_id=123, user=user)

El dispatcher `_REVERT_HANDLERS` mapea (entidad, accion) -> función que
sabe deshacer ese caso concreto. Si una entidad/acción no tiene handler,
se intenta un undo genérico basado en el snapshot_antes.
"""
from __future__ import annotations

import json
from datetime import datetime, date
from typing import Any, Optional, Callable
from sqlalchemy.orm import Session
from sqlalchemy import inspect as sa_inspect

from app import models


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------
def _json_default(v: Any) -> Any:
    """Serializador defensivo para tipos no-JSON nativos."""
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if hasattr(v, "value"):  # Enum
        return v.value
    return str(v)


def snapshot(obj) -> dict:
    """Devuelve un dict serializable con el estado actual de una entidad ORM.

    No incluye relaciones — solo columnas, para que el dict pueda usarse
    como input a `_restore_from_snapshot()` sin sorpresas.
    """
    if obj is None:
        return None
    mapper = sa_inspect(obj).mapper
    out: dict = {}
    for col in mapper.columns:
        val = getattr(obj, col.key)
        if isinstance(val, (datetime, date)):
            out[col.key] = val.isoformat()
        elif hasattr(val, "value"):  # Enum
            out[col.key] = val.value
        else:
            out[col.key] = val
    return out


def _dumps(d: Optional[dict]) -> Optional[str]:
    if d is None:
        return None
    return json.dumps(d, default=_json_default, ensure_ascii=False)


def _loads(s: Optional[str]) -> Optional[dict]:
    if not s:
        return None
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------
def registrar(
    db: Session,
    user,
    *,
    entidad: str,
    entidad_id: Optional[int],
    accion: models.AccionTipo,
    descripcion: str,
    antes: Optional[dict] = None,
    despues: Optional[dict] = None,
    revertible: bool = True,
) -> models.AccionHistorial:
    """Inserta una fila en `acciones_historial`. NO hace commit — el caller
    es responsable de commitear en la misma transacción que su cambio.
    """
    accion_row = models.AccionHistorial(
        user_id=getattr(user, "id", None),
        user_nombre=getattr(user, "nombre", None) or getattr(user, "email", None),
        entidad=entidad,
        entidad_id=entidad_id,
        accion=accion,
        descripcion=descripcion[:500] if descripcion else "",
        snapshot_antes=_dumps(antes),
        snapshot_despues=_dumps(despues),
        revertible=revertible,
    )
    db.add(accion_row)
    db.flush()  # para tener el id sin commitear
    return accion_row


# ---------------------------------------------------------------------------
# Reversión
# ---------------------------------------------------------------------------
class RevertError(Exception):
    """La acción no se puede revertir por motivos de negocio."""


def _model_for(entidad: str):
    """Mapea nombre de tabla -> clase modelo."""
    mapping = {
        "pagos": models.Pago,
        "contratos": models.Contrato,
        "ajustes_contrato": models.AjusteContrato,
        "clientes": models.Cliente,
        "propiedades": models.Propiedad,
        "refacciones": models.Refaccion,
    }
    return mapping.get(entidad)


def _restore_from_snapshot(db: Session, model_cls, snap: dict) -> Any:
    """Reconstruye o re-actualiza una fila a partir de un snapshot."""
    pk = snap.get("id")
    obj = db.query(model_cls).get(pk) if pk else None

    # Convertir ISO strings a date/datetime según el tipo de columna
    mapper = sa_inspect(model_cls)
    typed = {}
    for col in mapper.columns:
        if col.key not in snap:
            continue
        val = snap[col.key]
        col_type = str(col.type).lower()
        if val is not None and isinstance(val, str):
            try:
                if "datetime" in col_type or "timestamp" in col_type:
                    val = datetime.fromisoformat(val)
                elif "date" in col_type:
                    val = date.fromisoformat(val)
            except (ValueError, TypeError):
                pass
        typed[col.key] = val

    if obj is None:
        # Fue eliminado: recrear
        obj = model_cls(**typed)
        db.add(obj)
    else:
        for k, v in typed.items():
            setattr(obj, k, v)
    return obj


# Dispatcher
# Cada handler recibe (db, accion_row, user) y debe deshacer la acción.
# Si no hay handler específico, se usa _undo_generic basado en accion.accion.
_REVERT_HANDLERS: dict[tuple, Callable] = {}


def revert_handler(entidad: str, accion: models.AccionTipo):
    """Decorador para registrar handlers específicos."""
    def deco(fn):
        _REVERT_HANDLERS[(entidad, accion)] = fn
        return fn
    return deco


def _undo_generic(db: Session, accion_row: models.AccionHistorial, user):
    """Reversión genérica basada en el snapshot_antes.

    - create  -> borrar la fila creada (entidad_id)
    - update  -> restaurar valores anteriores
    - delete  -> recrear la fila con el snapshot_antes
    """
    entidad = accion_row.entidad
    model_cls = _model_for(entidad)
    if model_cls is None:
        raise RevertError(f"No hay modelo registrado para '{entidad}'")

    if accion_row.accion == models.AccionTipo.create:
        if not accion_row.entidad_id:
            raise RevertError("No se puede revertir create sin entidad_id")
        obj = db.query(model_cls).get(accion_row.entidad_id)
        if obj is None:
            return  # ya no existe — undo idempotente
        db.delete(obj)
        return

    if accion_row.accion == models.AccionTipo.delete:
        snap = _loads(accion_row.snapshot_antes)
        if not snap:
            raise RevertError("Snapshot anterior vacío — no se puede recrear")
        _restore_from_snapshot(db, model_cls, snap)
        return

    if accion_row.accion in (models.AccionTipo.update, models.AccionTipo.cobrar,
                              models.AccionTipo.aplicar_ajuste):
        snap = _loads(accion_row.snapshot_antes)
        if not snap:
            raise RevertError("Snapshot anterior vacío — no se puede restaurar")
        _restore_from_snapshot(db, model_cls, snap)
        return

    raise RevertError(f"Acción '{accion_row.accion}' no tiene undo definido")


# Handler especial para `registrar_pago`: marca el pago como pendiente +
# borra el comprobante asociado si existe.
@revert_handler("pagos", models.AccionTipo.registrar_pago)
def _undo_registrar_pago(db: Session, accion_row: models.AccionHistorial, user):
    snap_antes = _loads(accion_row.snapshot_antes)
    if not snap_antes:
        raise RevertError("Snapshot del pago anterior no disponible")

    pago = db.query(models.Pago).get(accion_row.entidad_id)
    if pago is None:
        raise RevertError("El pago ya no existe")

    # Borrar comprobantes generados a partir de este pago
    db.query(models.Comprobante).filter_by(pago_id=pago.id).delete()

    # Restaurar el pago al estado previo
    _restore_from_snapshot(db, models.Pago, snap_antes)


def revertir(db: Session, accion_id: int, user, *, motivo: Optional[str] = None) -> models.AccionHistorial:
    """Revierte una acción previamente registrada. NO commitea — el caller decide."""
    accion_row = db.query(models.AccionHistorial).get(accion_id)
    if accion_row is None:
        raise RevertError("Acción no encontrada")
    if not accion_row.revertible:
        raise RevertError("Esta acción está marcada como no revertible")
    if accion_row.revertida:
        raise RevertError("Esta acción ya fue revertida")

    handler = _REVERT_HANDLERS.get((accion_row.entidad, accion_row.accion))
    if handler:
        handler(db, accion_row, user)
    else:
        _undo_generic(db, accion_row, user)

    # Marcar como revertida + dejar rastro
    accion_row.revertida = True
    accion_row.revertida_at = datetime.utcnow()
    accion_row.revertida_by_id = getattr(user, "id", None)
    accion_row.revertida_motivo = (motivo or "")[:500]

    # Registrar la reversión COMO una acción más, para que quede en el log
    registrar(
        db, user,
        entidad=accion_row.entidad,
        entidad_id=accion_row.entidad_id,
        accion=models.AccionTipo.update,
        descripcion=f"Revirtió acción #{accion_row.id} ({accion_row.descripcion})",
        antes=None,
        despues=None,
        revertible=False,  # no se puede re-revertir una reversión desde acá
    )

    return accion_row
