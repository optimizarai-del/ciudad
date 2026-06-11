"""
Post-venta automática (Fase 3, plan sección 8).

Al cerrar una operación se generan tareas de seguimiento según las plantillas
activas (default 30 / 180 / 365 días desde el cierre). Un job diario marca las
tareas vencidas y deja una notificación para el vendedor.
"""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app import models_ventas as mv

DEFAULT_OFFSETS = [
    ("Seguimiento 30 días", 30),
    ("Seguimiento 6 meses", 180),
    ("Seguimiento 1 año", 365),
]


def asegurar_plantillas_default(db: Session):
    """Crea las plantillas default si no hay ninguna."""
    if db.query(mv.VentasPlantillaSeguimiento).count() == 0:
        for nombre, dias in DEFAULT_OFFSETS:
            db.add(mv.VentasPlantillaSeguimiento(nombre=nombre, offset_dias=dias, activa=True))
        db.flush()


def generar_tareas_postventa(db: Session, operacion: mv.VentasOperacion) -> int:
    """Genera las tareas de seguimiento para una operación cerrada. Idempotente:
    no duplica si ya existen tareas para esa operación."""
    base = operacion.fecha_cierre or date.today()
    ya = db.query(mv.VentasTarea).filter_by(operacion_id=operacion.id).count()
    if ya:
        return 0
    asegurar_plantillas_default(db)
    plantillas = (db.query(mv.VentasPlantillaSeguimiento)
                  .filter_by(activa=True).order_by(mv.VentasPlantillaSeguimiento.offset_dias).all())
    creadas = 0
    for pl in plantillas:
        db.add(mv.VentasTarea(
            vendedor_id=operacion.vendedor_id,
            cliente_id=operacion.cliente_id,
            operacion_id=operacion.id,
            tipo=mv.TareaTipo.seguimiento_postventa,
            descripcion=f"{pl.nombre} — contactar al cliente post-venta",
            vencimiento=base + timedelta(days=pl.offset_dias),
            estado=mv.TareaEstado.pendiente,
        ))
        creadas += 1
    db.flush()
    return creadas


def marcar_vencidas(db: Session) -> list:
    """Marca como vencidas las tareas pendientes cuya fecha ya pasó.
    Devuelve la lista de tareas recién vencidas (para notificar)."""
    hoy = date.today()
    pendientes = (db.query(mv.VentasTarea)
                  .filter(mv.VentasTarea.estado == mv.TareaEstado.pendiente,
                          mv.VentasTarea.vencimiento != None,  # noqa: E711
                          mv.VentasTarea.vencimiento <= hoy).all())
    recien = []
    for t in pendientes:
        t.estado = mv.TareaEstado.vencida
        recien.append(t)
    db.flush()
    return recien
