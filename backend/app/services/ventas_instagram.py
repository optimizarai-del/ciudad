"""
Radar Instagram — scraping de publicaciones de cuentas que seguimos.

Fuente: actor `apify/instagram-scraper` de Apify vía run-sync-get-dataset-items
(no usa tu cuenta de IG → sin riesgo de ban). Sin `APIFY_TOKEN` configurado,
cae a un MODO MOCK con posts de ejemplo deterministas, así toda la UI
(cargar cuentas → correr → listar → analizar) se puede probar sin gastar crédito.

Expone:
  - scrapear_cuenta(username, limite) -> list[dict] normalizados
  - correr_scrape(db, cuentas, limite) -> resumen (hace upsert idempotente)
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx

from app import models_ventas as mv

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(180.0, connect=15.0)

APIFY_ACTOR = os.getenv("APIFY_ACTOR", "apify/instagram-scraper")
MAX_POSTS_DEFAULT = int(os.getenv("IG_SCRAPER_MAX_POSTS", "12") or 12)


def _token() -> str:
    return os.getenv("APIFY_TOKEN", "").strip()


def _apify_input(username: str, limite: int) -> dict[str, Any]:
    """Input del actor apify/instagram-scraper para traer los últimos posts
    de un perfil puntual."""
    u = username.strip().lstrip("@").lower()
    return {
        "directUrls": [f"https://www.instagram.com/{u}/"],
        "resultsType": "posts",
        "resultsLimit": limite,
        "addParentData": False,
    }


# ── Parseo liviano del caption ───────────────────────────────────────────────
_RE_PRECIO = re.compile(
    r"(u\$s|us\$|usd|\$|ar\$)\s?\.?\s?([\d][\d\.\,]{2,})", re.IGNORECASE
)


def _parse_operacion(caption: str) -> str | None:
    t = (caption or "").lower()
    venta = any(k in t for k in ("venta", "vende", "en venta", "se vende", "vendo"))
    alq = any(k in t for k in ("alquiler", "alquila", "renta", "alquilo", "en alquiler"))
    if venta and not alq:
        return "venta"
    if alq and not venta:
        return "alquiler"
    if venta and alq:
        return "venta/alquiler"
    return None


def _parse_precio(caption: str) -> str | None:
    m = _RE_PRECIO.search(caption or "")
    if not m:
        return None
    simbolo = m.group(1).upper().replace("U$S", "USD").replace("US$", "USD")
    numero = m.group(2).strip().rstrip(".,")   # sin puntuación final ("120.000." → "120.000")
    return f"{simbolo} {numero}".strip()


# ── Normalización de un item de Apify a nuestro contrato común ───────────────
def _to_dt(ts: Any) -> datetime | None:
    if not ts:
        return None
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
        # ISO string tipo "2026-07-01T12:00:00.000Z"
        s = str(ts).replace("Z", "+00:00")
        return datetime.fromisoformat(s).replace(tzinfo=None)
    except Exception:
        return None


def _normalizar(item: dict, cuenta_username: str) -> dict[str, Any]:
    caption = item.get("caption") or item.get("text") or ""
    short = item.get("shortCode") or item.get("code") or item.get("id") or ""
    url = item.get("url") or (f"https://www.instagram.com/p/{short}/" if short else "")
    tipo_raw = (item.get("type") or "").lower()
    tipo = {"image": "image", "video": "video", "sidecar": "sidecar"}.get(tipo_raw, tipo_raw or "image")
    return {
        "ig_post_id": str(item.get("id") or short or url),
        "url": url,
        "caption": caption,
        "imagen_url": item.get("displayUrl") or item.get("imageUrl") or "",
        "tipo": tipo,
        "fecha_post": _to_dt(item.get("timestamp") or item.get("takenAtTimestamp")),
        "likes": int(item.get("likesCount") or 0),
        "comentarios": int(item.get("commentsCount") or 0),
        "autor_username": (item.get("ownerUsername") or cuenta_username or "").lstrip("@").lower(),
        "autor_nombre": item.get("ownerFullName") or "",
        "autor_foto": item.get("ownerProfilePicUrl") or "",
        "operacion": _parse_operacion(caption),
        "precio_texto": _parse_precio(caption),
    }


def scrapear_cuenta(username: str, limite: int | None = None) -> list[dict[str, Any]]:
    """Devuelve los últimos posts (normalizados) de una cuenta. Apify si hay
    token; si no, modo mock."""
    limite = min(int(limite or MAX_POSTS_DEFAULT), 50)
    u = username.strip().lstrip("@").lower()
    if not u:
        return []

    if not _token():
        logger.warning("APIFY_TOKEN no configurado — MODO MOCK para @%s.", u)
        return [_normalizar(it, u) for it in _mock_posts(u, min(limite, 8))]

    actor = APIFY_ACTOR.replace("/", "~")  # la API usa ~ como separador
    url = f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, params={"token": _token()}, json=_apify_input(u, limite))
            resp.raise_for_status()
            data = resp.json()
            items = data if isinstance(data, list) else data.get("items", [])
            return [_normalizar(it, u) for it in items if isinstance(it, dict)]
    except httpx.HTTPError as e:
        logger.error("Apify falló para @%s: %s", u, e)
        raise RuntimeError(f"Error consultando Apify: {e}") from e


def _mock_posts(username: str, n: int) -> list[dict[str, Any]]:
    """Posts de ejemplo deterministas (dev/demo sin token)."""
    tipos = ["Casa 3 amb", "Departamento 2 amb", "Lote", "PH", "Local comercial"]
    zonas = ["Santa Rosa", "Toay", "General Pico", "B° España", "Centro"]
    ops = ["EN VENTA", "EN ALQUILER"]
    out = []
    for i in range(n):
        seed = int(hashlib.sha256(f"{username}{i}".encode()).hexdigest(), 16)
        op = ops[seed % 2]
        precio = 40000 + (seed % 200000)
        tipo = tipos[seed % len(tipos)]
        zona = zonas[seed % len(zonas)]
        moneda = "USD" if op == "EN VENTA" else "$"
        cap = f"{op} — {tipo} en {zona}. {moneda} {precio:,}. Consultas por DM. #{zona.replace(' ','')} #propiedades"
        out.append({
            "id": f"mock_{username}_{i}",
            "shortCode": f"MK{seed % 1000000:06d}",
            "url": f"https://www.instagram.com/p/MK{seed % 1000000:06d}/",
            "caption": cap,
            "displayUrl": f"https://picsum.photos/seed/{username}{i}/600/600",
            "type": "image",
            "timestamp": 1751000000 + i * 86400,
            "likesCount": seed % 500,
            "commentsCount": seed % 40,
            "ownerUsername": username,
            "ownerFullName": f"{username.capitalize()} Propiedades",
            "ownerProfilePicUrl": f"https://picsum.photos/seed/{username}pfp/80/80",
        })
    return out


# ── Upsert idempotente + corrida ────────────────────────────────────────────
def _upsert_publicaciones(db, cuenta: mv.IgCuenta, posts: list[dict]) -> int:
    """Inserta los posts que no existan (dedup por workspace_id + ig_post_id).
    Devuelve cuántos nuevos se crearon."""
    nuevas = 0
    for p in posts:
        pid = p.get("ig_post_id")
        if not pid:
            continue
        existe = (
            db.query(mv.IgPublicacion.id)
            .filter(
                mv.IgPublicacion.workspace_id == (cuenta.workspace_id or mv.WORKSPACE_DEFAULT),
                mv.IgPublicacion.ig_post_id == pid,
            )
            .first()
        )
        if existe:
            continue
        db.add(mv.IgPublicacion(
            workspace_id=cuenta.workspace_id or mv.WORKSPACE_DEFAULT,
            is_demo=bool(cuenta.is_demo),
            cuenta_id=cuenta.id,
            ig_post_id=pid,
            url=p.get("url"),
            caption=p.get("caption"),
            imagen_url=p.get("imagen_url"),
            tipo=p.get("tipo"),
            fecha_post=p.get("fecha_post"),
            likes=p.get("likes") or 0,
            comentarios=p.get("comentarios") or 0,
            autor_username=p.get("autor_username"),
            autor_nombre=p.get("autor_nombre"),
            autor_foto=p.get("autor_foto"),
            operacion=p.get("operacion"),
            precio_texto=p.get("precio_texto"),
        ))
        nuevas += 1
    return nuevas


def correr_scrape(db, cuentas: Iterable[mv.IgCuenta], limite: int | None = None) -> dict:
    """Scrapea cada cuenta y hace upsert de sus posts. Actualiza el estado de
    la cuenta. NO hace commit — lo decide el caller. Devuelve un resumen."""
    total_nuevas = 0
    detalle = []
    ahora = datetime.utcnow()
    for c in cuentas:
        try:
            posts = scrapear_cuenta(c.username, limite)
            nuevas = _upsert_publicaciones(db, c, posts)
            c.ultima_corrida = ahora
            c.ultimo_estado = "ok"
            c.ultimo_nuevas = nuevas
            total_nuevas += nuevas
            detalle.append({"cuenta": c.username, "posts": len(posts), "nuevas": nuevas})
        except Exception as e:
            msg = f"{type(e).__name__}: {str(e)[:180]}"
            c.ultima_corrida = ahora
            c.ultimo_estado = f"error: {msg}"[:250]
            c.ultimo_nuevas = 0
            logger.error("[ig] scrape @%s falló: %s", c.username, msg)
            detalle.append({"cuenta": c.username, "error": msg})
    return {
        "cuentas": len(detalle),
        "nuevas": total_nuevas,
        "usando_mock": not bool(_token()),
        "detalle": detalle,
    }


# ── Corrida diaria automática (loop en proceso, opt-in) ──────────────────────
def correr_todas_las_cuentas(limite: int | None = None) -> dict:
    """Scrapea todas las cuentas activas (todos los workspaces). Crea y cierra
    su propia sesión. Idempotente: no duplica publicaciones."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        # Solo cuentas REALES en la corrida automática (no gastar crédito de
        # Apify en el sandbox demo, que se scrapea a mano desde la UI).
        cuentas = db.query(mv.IgCuenta).filter(
            mv.IgCuenta.activa.is_(True), mv.IgCuenta.is_demo.is_(False)
        ).all()
        resumen = correr_scrape(db, cuentas, limite)
        db.commit()
        print(f"[ig-diario] {resumen.get('cuentas')} cuentas, {resumen.get('nuevas')} nuevas")
        return resumen
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        print(f"[ig-diario] error: {e}")
        return {"error": str(e)}
    finally:
        db.close()


async def loop_scrape_ig(intervalo_seg: int = 86400):
    """Loop de fondo: corre la corrida diaria cada `intervalo_seg` (24 h).
    La parte bloqueante (httpx + DB) corre en un thread para no frenar el event
    loop. Se arranca desde el startup de main.py si IG_SCRAPER_ENABLED."""
    import asyncio
    while True:
        try:
            await asyncio.to_thread(correr_todas_las_cuentas)
        except Exception as e:
            print(f"[ig-diario] ciclo falló: {e}")
        await asyncio.sleep(intervalo_seg)
