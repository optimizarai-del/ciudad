"""Helper de notificaciones del módulo Ventas (Fase 2/3)."""
import json

from sqlalchemy.orm import Session

from app import models_ventas as mv
from app.services import ventas_telegram


def crear_notificacion(db: Session, vendedor_id, tipo, titulo, cuerpo, payload=None,
                       enviar_telegram=True):
    """Crea una notificación persistida y, si corresponde, la manda por Telegram."""
    n = mv.VentasNotificacion(
        vendedor_id=vendedor_id, tipo=tipo, titulo=titulo, cuerpo=cuerpo,
        payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
    )
    db.add(n); db.flush()
    if enviar_telegram:
        ok = ventas_telegram.enviar_a_vendedor(db, vendedor_id, f"{titulo}\n{cuerpo}")
        if ok:
            n.enviada_telegram = True
    return n
