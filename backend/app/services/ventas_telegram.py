"""
Bot de Telegram del módulo Ventas (Fase 2).

Degradación elegante: si no hay `VENTAS_TELEGRAM_BOT_TOKEN` configurado, las
funciones de envío no fallan — registran que no se pudo enviar y siguen. Toda
la lógica de vinculación (token one-time) y de parseo de comandos funciona sin
el bot vivo, para poder testear y conectar el token cuando esté disponible.

La vinculación: el vendedor genera un token desde la web (TTL 10 min) y se lo
manda al bot como `/start <token>`. El webhook lo recibe, valida el token y
asocia el chat_id al vendedor.
"""
import os
import json
import secrets
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import models_ventas as mv

TOKEN_TTL_MIN = 10


def _bot_token():
    return os.getenv("VENTAS_TELEGRAM_BOT_TOKEN", "").strip()


def bot_disponible() -> bool:
    return bool(_bot_token())


def generar_token_vinculacion(db: Session, vendedor_id: int) -> dict:
    """Genera (o regenera) un token one-time para vincular Telegram."""
    link = db.query(mv.VentasTelegramLink).filter_by(vendedor_id=vendedor_id).first()
    token = secrets.token_urlsafe(8)
    expira = datetime.utcnow() + timedelta(minutes=TOKEN_TTL_MIN)
    if not link:
        link = mv.VentasTelegramLink(vendedor_id=vendedor_id)
        db.add(link)
    link.token = token
    link.token_expira = expira
    # Si regenera token, mantiene vinculado si ya lo estaba.
    db.flush()
    return {"token": token, "expira": expira.isoformat(),
            "instruccion": f"Abrí el bot y mandá:  /start {token}"}


def confirmar_vinculacion(db: Session, token: str, chat_id: str) -> bool:
    """Procesa un /start <token> entrante. Devuelve True si vinculó."""
    link = db.query(mv.VentasTelegramLink).filter_by(token=token).first()
    if not link or not link.token_expira or link.token_expira < datetime.utcnow():
        return False
    link.chat_id = str(chat_id)
    link.vinculado = True
    link.token = None
    link.token_expira = None
    db.flush()
    return True


def enviar_a_vendedor(db: Session, vendedor_id: int, texto: str) -> bool:
    """Envía un mensaje por Telegram al vendedor. Devuelve True si se envió."""
    link = db.query(mv.VentasTelegramLink).filter_by(
        vendedor_id=vendedor_id, vinculado=True).first()
    if not link or not link.chat_id:
        return False
    return _enviar_mensaje(link.chat_id, texto)


def _enviar_mensaje(chat_id: str, texto: str) -> bool:
    token = _bot_token()
    if not token:
        print(f"[ventas_telegram] (sin token) mensaje a {chat_id}: {texto[:60]}")
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": texto}).encode()
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status == 200
    except Exception as e:
        print(f"[ventas_telegram] error enviando: {e}")
        return False
