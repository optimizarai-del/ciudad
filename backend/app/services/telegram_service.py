import os
import httpx

TELEGRAM_API = "https://api.telegram.org/bot{token}"

async def send_message(chat_id: str, text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json={"chat_id": chat_id, "text": text})
        return resp.status_code == 200

async def send_typing(chat_id: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return
    url = f"https://api.telegram.org/bot{token}/sendChatAction"
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(url, json={"chat_id": chat_id, "action": "typing"})
