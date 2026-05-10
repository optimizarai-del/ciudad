import os
import httpx
from typing import Optional

WHATSAPP_API = "https://graph.facebook.com/v19.0"
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")


async def send_message(to: str, text: str) -> bool:
    """Envía un mensaje de texto por WhatsApp Business API."""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        print("WhatsApp no configurado: faltan WHATSAPP_TOKEN o WHATSAPP_PHONE_ID")
        return False

    url = f"{WHATSAPP_API}/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return True
    except httpx.HTTPError as e:
        print(f"Error enviando WhatsApp a {to}: {e}")
        return False


async def mark_read(message_id: str) -> bool:
    """Marca un mensaje de WhatsApp como leído."""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        return False

    url = f"{WHATSAPP_API}/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return True
    except httpx.HTTPError as e:
        print(f"Error marcando como leído {message_id}: {e}")
        return False


async def send_template(to: str, template_name: str, language: str = "es", components: Optional[list] = None) -> bool:
    """Envía un mensaje de plantilla aprobada por WhatsApp."""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        return False

    url = f"{WHATSAPP_API}/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    template = {
        "name": template_name,
        "language": {"code": language},
    }
    if components:
        template["components"] = components

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": template,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return True
    except httpx.HTTPError as e:
        print(f"Error enviando template {template_name} a {to}: {e}")
        return False
