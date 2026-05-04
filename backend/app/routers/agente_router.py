"""
Router del Agente IA de Ciudad.

Endpoints:
  POST /api/agente/webhook/telegram   <- webhook del bot de Telegram
  GET  /api/agente/webhook/instagram  <- verificación de Instagram
  POST /api/agente/webhook/instagram  <- mensajes de Instagram (preparado)
  POST /api/agente/chat               <- chat de prueba desde el panel
  GET  /api/agente/leads              <- lista de leads con historial
  GET  /api/agente/leads/{id}         <- detalle de un lead
  PATCH /api/agente/leads/{id}        <- actualizar estado/notas
  GET  /api/agente/stats              <- estadísticas del agente
"""
import asyncio
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Request, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app import models
from app.services import agente_service, telegram_service

router = APIRouter(prefix="/api/agente", tags=["agente"])


# ── Schemas ───────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    mensaje: str
    canal_id: str = "test_panel"
    canal: str = "web"

class LeadUpdate(BaseModel):
    estado: Optional[str] = None
    notas_crm: Optional[str] = None
    nombre: Optional[str] = None
    telefono: Optional[str] = None


# ── Telegram webhook ──────────────────────────────────────────────────────────
@router.post("/webhook/telegram")
async def telegram_webhook(request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    data = await request.json()
    message = data.get("message") or data.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = str(message["chat"]["id"])
    text = message.get("text", "")
    username = message.get("from", {}).get("username", "")

    if not text:
        return {"ok": True}

    async def _process():
        await telegram_service.send_typing(chat_id)
        oraciones = await agente_service.procesar_mensaje(
            canal_id=chat_id,
            texto=text,
            canal="telegram",
            db=db,
            username=username,
            usar_debounce=True,
        )
        for oracion in oraciones:
            await telegram_service.send_message(chat_id, oracion)
            await asyncio.sleep(3)

    background.add_task(_process)
    return {"ok": True}


# ── Instagram webhook ─────────────────────────────────────────────────────────
@router.get("/webhook/instagram")
async def instagram_verify(request: Request):
    """Verificación de webhook de Instagram (Meta)."""
    params = request.query_params
    verify_token = os.getenv("INSTAGRAM_VERIFY_TOKEN", "ciudad_verify_token")
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == verify_token
    ):
        return int(params.get("hub.challenge", 0))
    raise HTTPException(403, "Token de verificación inválido")


@router.post("/webhook/instagram")
async def instagram_webhook(request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Webhook de Instagram Direct Messages.
    Preparado para activación — requiere:
      1. INSTAGRAM_VERIFY_TOKEN en .env
      2. INSTAGRAM_PAGE_ACCESS_TOKEN en .env
      3. Registrar el webhook en Meta Business Suite
    """
    data = await request.json()
    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event.get("sender", {}).get("id", "")
            text = event.get("message", {}).get("text", "")
            caption = ""
            # Si respondió a un post, capturar caption
            reply_to = event.get("message", {}).get("reply_to", {})
            if reply_to:
                caption = reply_to.get("story", {}).get("url", "")

            if sender_id and text:
                async def _process(sid=sender_id, t=text, cap=caption):
                    oraciones = await agente_service.procesar_mensaje(
                        canal_id=sid,
                        texto=t,
                        canal="instagram",
                        db=db,
                        usar_debounce=True,
                        caption_post=cap,
                    )
                    # TODO: enviar via Instagram Graph API
                    # await instagram_service.send_message(sid, oracion)

                background.add_task(_process)

    return {"ok": True}


# ── Chat de prueba (panel Ciudad) ─────────────────────────────────────────────
@router.post("/chat")
async def chat_test(req: ChatRequest, db: Session = Depends(get_db)):
    """Endpoint para probar el agente desde el panel de Ciudad (sin debounce)."""
    oraciones = await agente_service.procesar_mensaje(
        canal_id=req.canal_id,
        texto=req.mensaje,
        canal=req.canal,
        db=db,
        usar_debounce=False,
    )
    return {"respuesta": " ".join(oraciones), "oraciones": oraciones}


# ── Leads ─────────────────────────────────────────────────────────────────────
@router.get("/leads")
def listar_leads(estado: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.Lead)
    if estado:
        q = q.filter(models.Lead.estado == estado)
    leads = q.order_by(models.Lead.ultima_actividad.desc()).all()
    result = []
    for l in leads:
        msgs = db.query(models.MensajeConversacion).filter_by(lead_id=l.id).order_by(
            models.MensajeConversacion.created_at.desc()
        ).limit(1).first()
        result.append({
            "id": l.id,
            "canal": l.canal,
            "canal_username": l.canal_username,
            "nombre": l.nombre,
            "telefono": l.telefono,
            "estado": l.estado,
            "operacion": l.operacion,
            "tipo_propiedad": l.tipo_propiedad,
            "zona": l.zona,
            "notas_crm": l.notas_crm,
            "ultimo_mensaje": msgs.contenido[:80] if msgs else "",
            "ultima_actividad": l.ultima_actividad.isoformat() if l.ultima_actividad else None,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        })
    return result


@router.get("/leads/{lead_id}")
def detalle_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(models.Lead).get(lead_id)
    if not lead:
        raise HTTPException(404, "Lead no encontrado")
    msgs = db.query(models.MensajeConversacion).filter_by(lead_id=lead.id).order_by(
        models.MensajeConversacion.created_at
    ).all()
    return {
        "id": lead.id,
        "canal": lead.canal,
        "canal_id": lead.canal_id,
        "canal_username": lead.canal_username,
        "nombre": lead.nombre,
        "telefono": lead.telefono,
        "email": lead.email,
        "estado": lead.estado,
        "operacion": lead.operacion,
        "tipo_propiedad": lead.tipo_propiedad,
        "zona": lead.zona,
        "habitaciones": lead.habitaciones,
        "presupuesto": lead.presupuesto,
        "notas_crm": lead.notas_crm,
        "ultima_actividad": lead.ultima_actividad.isoformat() if lead.ultima_actividad else None,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "conversacion": [
            {
                "rol": m.rol,
                "contenido": m.contenido,
                "created_at": m.created_at.isoformat()
            } for m in msgs
        ]
    }


@router.patch("/leads/{lead_id}")
def actualizar_lead(lead_id: int, data: LeadUpdate, db: Session = Depends(get_db)):
    lead = db.query(models.Lead).get(lead_id)
    if not lead:
        raise HTTPException(404, "Lead no encontrado")
    if data.estado:
        lead.estado = data.estado
    if data.notas_crm is not None:
        lead.notas_crm = data.notas_crm
    if data.nombre:
        lead.nombre = data.nombre
    if data.telefono:
        lead.telefono = data.telefono
    db.commit()
    return {"ok": True}


# ── Stats ─────────────────────────────────────────────────────────────────────
@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    total = db.query(models.Lead).count()
    nuevos = db.query(models.Lead).filter_by(estado=models.LeadEstado.nuevo).count()
    interesados = db.query(models.Lead).filter_by(estado=models.LeadEstado.interesado).count()
    a_contactar = db.query(models.Lead).filter_by(estado=models.LeadEstado.a_contactar).count()
    hoy = datetime.utcnow().date()
    hoy_count = db.query(models.Lead).filter(
        models.Lead.created_at >= datetime(hoy.year, hoy.month, hoy.day)
    ).count()
    total_msgs = db.query(models.MensajeConversacion).count()

    telegram_ok = bool(os.getenv("TELEGRAM_BOT_TOKEN"))
    instagram_ok = bool(os.getenv("INSTAGRAM_PAGE_ACCESS_TOKEN"))

    return {
        "total_leads": total,
        "nuevos": nuevos,
        "interesados": interesados,
        "a_contactar": a_contactar,
        "leads_hoy": hoy_count,
        "total_mensajes": total_msgs,
        "canales": {
            "telegram": {"activo": telegram_ok, "nombre": "Telegram"},
            "instagram": {"activo": instagram_ok, "nombre": "Instagram", "pendiente": not instagram_ok},
        }
    }
