"""
Jobs diarios del módulo Ventas (Fase 3).

Pensado para dispararse desde un cron de Easypanel que pega a
`POST /api/ventas-crm/jobs/run-daily`. Concentra:
  - Marcar tareas vencidas y notificar al vendedor (post-venta).
  - Notificación diaria AGRUPADA de matches (Mod #9): un solo mensaje por
    vendedor con "Tenés X matches nuevos. Entrá a verlos 👉", respetando el
    horario configurado por vendedor (hora_notif_matches).

`hora` (opcional, "HH") permite que el cron corra cada hora y solo notifique a
los vendedores cuya hora coincide. Si es None, notifica a todos (uso manual/test).
"""
from collections import Counter

from sqlalchemy.orm import Session

from app import models_ventas as mv
from app.services import ventas_tareas
from app.services.ventas_notif import crear_notificacion


def _notif_tareas_vencidas(db: Session) -> int:
    recien = ventas_tareas.marcar_vencidas(db)
    por_vendedor = Counter(t.vendedor_id for t in recien if t.vendedor_id)
    for vendedor_id, n in por_vendedor.items():
        crear_notificacion(
            db, vendedor_id, mv.NotifTipo.tarea,
            "Tareas vencidas",
            f"Tenés {n} tarea(s) de seguimiento vencida(s). Revisalas en Tareas.",
            payload={"cantidad": n},
        )
    return len(recien)


def _notif_matches(db: Session, hora=None) -> int:
    """Mod #9: una notificación por vendedor agrupando sus matches nuevos."""
    pendientes = (db.query(mv.VentasMatch)
                  .filter(mv.VentasMatch.notificado == False,  # noqa: E712
                          mv.VentasMatch.estado == mv.MatchEstado.pendiente).all())
    por_vendedor = {}
    for m in pendientes:
        por_vendedor.setdefault(m.vendedor_id, []).append(m)

    notificados = 0
    for vendedor_id, matches in por_vendedor.items():
        if not vendedor_id:
            continue
        vend = db.query(mv.VentasVendedor).filter_by(id=vendedor_id).first()
        if not vend or not vend.notif_matches_activa:
            continue
        # Respetar el horario configurado del vendedor (si se pasó hora)
        if hora is not None:
            hh = (vend.hora_notif_matches or "09:00").split(":")[0]
            if hh != str(hora).zfill(2):
                continue
        crear_notificacion(
            db, vendedor_id, mv.NotifTipo.match,
            "Nuevos matches",
            f"Tenés {len(matches)} match(es) nuevo(s) hoy. Entrá a verlos 👉 /ventas-crm/matches",
            payload={"cantidad": len(matches)},
        )
        for m in matches:
            m.notificado = True
        notificados += len(matches)
    return notificados


def run_daily(db: Session, hora=None) -> dict:
    vencidas = _notif_tareas_vencidas(db)
    matches = _notif_matches(db, hora=hora)
    db.commit()
    return {"tareas_vencidas": vencidas, "matches_notificados": matches}
