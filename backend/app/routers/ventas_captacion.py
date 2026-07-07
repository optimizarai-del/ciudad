"""
Webhooks de captación multicanal (Fase 4.2 Instagram / 4.3 WhatsApp).

Reciben mensajes entrantes de canales externos y los convierten en leads del
CRM (ver services/ventas_captacion.py). Son endpoints PÚBLICOS: los llama la
plataforma (Meta / YCloud), no un usuario logueado. La seguridad es por token:

  - Verificación (GET):  Meta manda hub.verify_token → lo comparamos con el
    token configurado en el entorno y devolvemos hub.challenge.
  - Recepción (POST):    parseamos el payload y creamos el lead.

Env necesarias (ver .env.example):
  INSTAGRAM_VERIFY_TOKEN   token del webhook de Instagram (Meta)
  WHATSAPP_VERIFY_TOKEN    token del webhook de WhatsApp Cloud API (Meta)

Todo es best-effort: si el payload no matchea ningún formato conocido,
devolvemos 200 igual (Meta reintenta ante cualquier no-200, y no queremos
loops). Nada de esto rompe si las credenciales no están cargadas: el endpoint
existe y queda listo para pegar el token cuando se conecte la cuenta.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import ventas_captacion

router = APIRouter(prefix="/api/ventas-crm/webhooks", tags=["ventas-captacion"])


def _verificar(mode: str | None, token: str | None, challenge: str | None,
               env_var: str):
    """Handshake de verificación de Meta (hub.mode=subscribe)."""
    esperado = (os.getenv(env_var) or "").strip()
    if mode == "subscribe" and esperado and token == esperado:
        return PlainTextResponse(challenge or "")
    return PlainTextResponse("forbidden", status_code=403)


# ───────────────────────── Instagram (DMs) ─────────────────────────

@router.get("/instagram")
def instagram_verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
):
    return _verificar(hub_mode, hub_verify_token, hub_challenge,
                      "INSTAGRAM_VERIFY_TOKEN")


@router.post("/instagram")
async def instagram_inbound(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
    except Exception:
        return {"ok": True}

    creados = 0
    # Estructura Meta: entry[].messaging[] (DMs) con sender.id + message.text.
    for entry in (data.get("entry") or []):
        for m in (entry.get("messaging") or []):
            sender = (m.get("sender") or {}).get("id")
            texto = (m.get("message") or {}).get("text")
            if not sender:
                continue
            # No re-procesar los echos de mensajes que enviamos nosotros.
            if (m.get("message") or {}).get("is_echo"):
                continue
            res = ventas_captacion.crear_lead_entrante(
                db, nombre=f"IG {sender}", origen="instagram",
                handle=str(sender), mensaje=texto)
            creados += 1 if res.get("nuevo") else 0
    db.commit()
    return {"ok": True, "leads_nuevos": creados}


# ───────────────────────── WhatsApp ─────────────────────────

@router.get("/whatsapp")
def whatsapp_verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
):
    return _verificar(hub_mode, hub_verify_token, hub_challenge,
                      "WHATSAPP_VERIFY_TOKEN")


def _parse_whatsapp(data: dict) -> list[dict]:
    """Extrae [{telefono, nombre, texto}] de un payload de WhatsApp.

    Soporta dos formatos:
      - Meta Cloud API: entry[].changes[].value.messages[] + .contacts[]
      - YCloud:         whatsappInboundMessage.{from, text.body, ...}
    """
    salidas: list[dict] = []

    # ── Meta WhatsApp Cloud API ──
    for entry in (data.get("entry") or []):
        for change in (entry.get("changes") or []):
            value = change.get("value") or {}
            contactos = {c.get("wa_id"): (c.get("profile") or {}).get("name")
                         for c in (value.get("contacts") or [])}
            for msg in (value.get("messages") or []):
                if msg.get("type") not in (None, "text"):
                    # igual capturamos el lead aunque el cuerpo no sea texto
                    pass
                frm = msg.get("from")
                texto = (msg.get("text") or {}).get("body")
                salidas.append({
                    "telefono": frm,
                    "nombre": contactos.get(frm) or (f"WhatsApp {frm}" if frm else "WhatsApp"),
                    "texto": texto,
                })

    # ── YCloud ──
    ym = data.get("whatsappInboundMessage") or data.get("whatsapp_inbound_message")
    if isinstance(ym, dict):
        frm = ym.get("from")
        texto = (ym.get("text") or {}).get("body") if isinstance(ym.get("text"), dict) else ym.get("text")
        nombre = (ym.get("customerProfile") or {}).get("name") if isinstance(ym.get("customerProfile"), dict) else None
        salidas.append({
            "telefono": frm,
            "nombre": nombre or (f"WhatsApp {frm}" if frm else "WhatsApp"),
            "texto": texto,
        })

    return [s for s in salidas if s.get("telefono")]


@router.post("/whatsapp")
async def whatsapp_inbound(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
    except Exception:
        return {"ok": True}

    creados = 0
    for item in _parse_whatsapp(data):
        res = ventas_captacion.crear_lead_entrante(
            db, nombre=item["nombre"], origen="whatsapp",
            telefono=item["telefono"], mensaje=item.get("texto"))
        creados += 1 if res.get("nuevo") else 0
    db.commit()
    return {"ok": True, "leads_nuevos": creados}


# ───────────────────────── Formulario web genérico ─────────────────────────

@router.post("/web")
async def web_inbound(request: Request, db: Session = Depends(get_db)):
    """Alta de lead desde un formulario de la web pública (landing, contacto).

    Body JSON libre: {nombre, telefono, email, mensaje, origen?}.
    """
    try:
        data = await request.json()
    except Exception:
        data = {}
    res = ventas_captacion.crear_lead_entrante(
        db,
        nombre=data.get("nombre") or "",
        origen=(data.get("origen") or "web"),
        telefono=data.get("telefono"),
        email=data.get("email"),
        mensaje=data.get("mensaje"),
    )
    db.commit()
    return {"ok": True, **res}
