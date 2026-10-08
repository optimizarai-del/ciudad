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


def _handle(raw: str) -> str:
    """Normaliza una cuenta a su username puro (sin @, sin URL).

    Acepta lo que cargue el operador: '@casa', 'casa',
    'https://www.instagram.com/casa/', 'instagram.com/casa?hl=es'. Si viene una
    URL, se queda con el primer segmento del path (el perfil). Así una cuenta
    cargada como URL completa no rompe el scraper con un 400 de Apify."""
    u = (raw or "").strip().lower()
    # Sacar esquema y query/fragment
    u = re.sub(r"^https?://", "", u).split("?")[0].split("#")[0]
    # Si tiene dominio de instagram, quedarse con lo que sigue
    if "instagram.com/" in u:
        u = u.split("instagram.com/", 1)[1]
    # Primer segmento del path (evita /p/, /reel/, sub-rutas)
    u = u.strip("/").split("/")[0]
    return u.lstrip("@").strip()


def _apify_input(username: str, limite: int) -> dict[str, Any]:
    """Input del actor apify/instagram-scraper para traer los últimos posts
    de un perfil puntual."""
    u = _handle(username)
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
    """Lee el caption (texto + hashtags) para decidir si es venta o alquiler.
    Es la señal confiable y gratuita (no hay OCR de la imagen): la mayoría de
    las inmobiliarias escriben 'VENTA'/'ALQUILER' en la descripción."""
    t = (caption or "").lower()
    venta = any(k in t for k in (
        "venta", "vende", "en venta", "se vende", "vendo", "a la venta",
        "#venta", "#enventa", "oportunidad de venta"))
    alq = any(k in t for k in (
        "alquiler", "alquila", "alquilo", "en alquiler", "renta", "rento",
        "#alquiler", "#enalquiler", "alquiler temporario", "alquiler anual"))
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


# Dormitorios / ambientes: "3 dormitorios", "2 dorm", "monoambiente",
# "4 ambientes" (ambientes = dormitorios + 1 estar; lo guardamos como pista).
_RE_DORM = re.compile(r"(\d+)\s*(?:dormitorios?|dorm\.?|hab\.?|habitaciones?|cuartos?)", re.IGNORECASE)
_RE_AMB = re.compile(r"(\d+)\s*(?:ambientes?|amb\.?)", re.IGNORECASE)
# m²: "120 m2", "120 m²", "120 mts2", "120 metros cuadrados".
_RE_M2 = re.compile(r"([\d][\d\.\,]*)\s*(?:m2|m²|mts2?|metros\s*(?:cuadrados)?)", re.IGNORECASE)


def _parse_dormitorios(caption: str) -> int | None:
    t = caption or ""
    m = _RE_DORM.search(t)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    if re.search(r"monoambiente|mono\s*amb", t, re.IGNORECASE):
        return 1
    # Fallback: "N ambientes" → aprox N-1 dormitorios (mínimo 1).
    m = _RE_AMB.search(t)
    if m:
        try:
            return max(1, int(m.group(1)) - 1)
        except ValueError:
            return None
    return None


def _parse_m2(caption: str) -> float | None:
    m = _RE_M2.search(caption or "")
    if not m:
        return None
    raw = m.group(1).replace(".", "").replace(",", ".")
    try:
        val = float(raw)
    except ValueError:
        return None
    # Descartar valores absurdos (ruido tipo años o teléfonos).
    return val if 5 <= val <= 100000 else None


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
        "dormitorios": _parse_dormitorios(caption),
        "superficie_m2": _parse_m2(caption),
    }


def scrapear_cuenta(username: str, limite: int | None = None) -> list[dict[str, Any]]:
    """Devuelve los últimos posts (normalizados) de una cuenta. Apify si hay
    token; si no, modo mock."""
    limite = min(int(limite or MAX_POSTS_DEFAULT), 50)
    u = _handle(username)
    if not u:
        return []

    if not _token():
        logger.warning("APIFY_TOKEN no configurado — MODO MOCK para @%s.", u)
        return [_normalizar(it, u) for it in _mock_posts(u, min(limite, 8))]

    actor = APIFY_ACTOR.replace("/", "~")  # la API usa ~ como separador
    url = f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
    # El token va por header Authorization (NO como query param): así nunca queda
    # en la URL y no se filtra si httpx incluye la URL en el mensaje de error.
    headers = {"Authorization": f"Bearer {_token()}"}
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, headers=headers, json=_apify_input(u, limite))
            resp.raise_for_status()
            data = resp.json()
            items = data if isinstance(data, list) else data.get("items", [])
            return [_normalizar(it, u) for it in items if isinstance(it, dict)]
    except httpx.HTTPStatusError as e:
        # Mensaje SANITIZADO: solo status + cuenta. Nunca la URL/token ni el body
        # crudo de Apify (que en el request lleva el token en claro).
        code = e.response.status_code if e.response is not None else "?"
        logger.error("Apify falló para @%s: HTTP %s", u, code)
        detalle = ("la cuenta no existe o está mal cargada (revisá el usuario)"
                   if code == 400 else f"HTTP {code}")
        raise RuntimeError(f"Error consultando Apify para @{u}: {detalle}") from None
    except httpx.HTTPError as e:
        # Error de red/timeout: log con el tipo, sin exponer detalles al front.
        logger.error("Apify error de red para @%s: %s", u, type(e).__name__)
        raise RuntimeError(f"Error de conexión con Apify para @{u}.") from None


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
            dormitorios=p.get("dormitorios"),
            superficie_m2=p.get("superficie_m2"),
        ))
        nuevas += 1
    return nuevas


def filtrar_posts(posts: list[dict], operacion: str | None = None,
                  q: str | None = None, zona: str | None = None,
                  dorm_min: int | None = None, m2_min: float | None = None) -> list[dict]:
    """Filtra los posts traídos ANTES de guardarlos (se descartan los que no
    matchean, así no se gasta DB ni se ensucia la lista).

    - operacion: 'venta' | 'alquiler' → deja solo los que matchean. En 'venta'
      descarta los de alquiler puro (los que no se pudieron clasificar también
      se descartan, para asegurar que sean ventas).
    - q / zona: el caption tiene que CONTENER esa palabra/localidad.
    - dorm_min / m2_min: mínimo de dormitorios / m² leídos del caption. Si el
      post no declara el dato, no pasa el filtro (no podemos asegurarlo).
    """
    out = posts
    if operacion:
        op = operacion.strip().lower()
        if op in ("venta", "alquiler"):
            out = [p for p in out if (p.get("operacion") or "") in (op, "venta/alquiler")]
    for needle in (q, zona):
        if needle and needle.strip():
            n = needle.strip().lower()
            out = [p for p in out if n in (p.get("caption") or "").lower()]
    if dorm_min:
        out = [p for p in out if (p.get("dormitorios") or 0) >= dorm_min]
    if m2_min:
        out = [p for p in out if (p.get("superficie_m2") or 0) >= m2_min]
    return out


def correr_scrape(db, cuentas: Iterable[mv.IgCuenta], limite: int | None = None,
                  operacion: str | None = None, q: str | None = None,
                  zona: str | None = None, dorm_min: int | None = None,
                  m2_min: float | None = None) -> dict:
    """Scrapea cada cuenta y hace upsert de sus posts. Los filtros (operacion,
    q, zona, dorm_min, m2_min) se aplican ANTES de tocar la DB: solo se guardan
    los posts que matchean. Actualiza el estado de la cuenta. NO hace commit —
    lo decide el caller. Devuelve un resumen."""
    total_nuevas = 0
    total_descartados = 0
    detalle = []
    ahora = datetime.utcnow()
    for c in cuentas:
        try:
            posts = scrapear_cuenta(c.username, limite)
            traidos = len(posts)
            posts = filtrar_posts(posts, operacion, q, zona, dorm_min, m2_min)
            total_descartados += traidos - len(posts)
            nuevas = _upsert_publicaciones(db, c, posts)
            c.ultima_corrida = ahora
            c.ultimo_estado = "ok"
            c.ultimo_nuevas = nuevas
            total_nuevas += nuevas
            detalle.append({"cuenta": c.username, "traidos": traidos,
                            "tras_filtro": len(posts), "nuevas": nuevas})
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
        "descartados_por_filtro": total_descartados,
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
