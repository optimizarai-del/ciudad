"""
Cliente liviano para Supabase Storage usando httpx + REST API.

Sin SDK extra: leemos las dos credenciales del .env y hablamos HTTP directo.

  SUPABASE_URL          ej: https://vihgicrkkbdzmsampwis.supabase.co
  SUPABASE_SERVICE_KEY  service_role key (NO la publishable / anon)

Buckets que usamos:
  - ciudad-adjuntos     fotos / docs / planos de propiedades
  - ciudad-comprobantes PDFs de comprobantes y liquidaciones

Tipo de URLs:
  - Por defecto firmamos URLs con expiración (1h) para que solo quien tiene el
    JWT del backend pueda descargar adjuntos privados.

Si las env vars no están seteadas, `enabled()` devuelve False y los routers
caen al modo legacy (blob_b64 inline en la DB).
"""
import os
import uuid
import httpx
from typing import Optional


BUCKET_ADJUNTOS = "ciudad-adjuntos"
BUCKET_COMPROBANTES = "ciudad-comprobantes"


def _base_url() -> Optional[str]:
    u = os.getenv("SUPABASE_URL", "").rstrip("/")
    return u or None


def _service_key() -> Optional[str]:
    return os.getenv("SUPABASE_SERVICE_KEY") or None


def enabled() -> bool:
    return bool(_base_url() and _service_key())


def _headers(extra: Optional[dict] = None) -> dict:
    key = _service_key() or ""
    h = {
        "Authorization": f"Bearer {key}",
        "apikey": key,
    }
    if extra:
        h.update(extra)
    return h


def gen_path(prefix: str, original_name: str) -> str:
    """Path con UUID para evitar colisiones y caracteres raros."""
    safe_ext = ""
    if "." in original_name:
        safe_ext = "." + original_name.rsplit(".", 1)[-1].lower()[:10]
    return f"{prefix.rstrip('/')}/{uuid.uuid4().hex}{safe_ext}"


def ensure_buckets() -> tuple[bool, str]:
    """Idempotente: crea los buckets si no existen. Llamar una vez al startup."""
    if not enabled():
        return False, "Storage deshabilitado (faltan SUPABASE_URL / SUPABASE_SERVICE_KEY)"

    base = _base_url()
    created = []
    for bucket in (BUCKET_ADJUNTOS, BUCKET_COMPROBANTES):
        try:
            r = httpx.post(
                f"{base}/storage/v1/bucket",
                headers=_headers({"Content-Type": "application/json"}),
                json={"id": bucket, "name": bucket, "public": False},
                timeout=10,
            )
            if r.status_code in (200, 201):
                created.append(bucket)
            elif r.status_code == 409 or "already exists" in r.text.lower():
                pass  # ya existe — OK
            else:
                return False, f"Bucket '{bucket}' falló: {r.status_code} {r.text[:200]}"
        except Exception as e:
            return False, f"Conexión a Supabase Storage falló: {type(e).__name__}: {e}"
    return True, f"OK (creados: {created})" if created else "OK (ya existían)"


def upload(bucket: str, path: str, content: bytes, content_type: str = "application/octet-stream") -> tuple[bool, str]:
    """Sube `content` al bucket/path. Devuelve (ok, msg-o-path)."""
    if not enabled():
        return False, "Storage no configurado"
    base = _base_url()
    try:
        r = httpx.post(
            f"{base}/storage/v1/object/{bucket}/{path}",
            headers=_headers({
                "Content-Type": content_type,
                "x-upsert": "true",
            }),
            content=content,
            timeout=30,
        )
        if r.status_code in (200, 201):
            return True, path
        return False, f"upload {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def get_signed_url(bucket: str, path: str, expires_in: int = 3600) -> tuple[bool, str]:
    """Genera una URL firmada (default 1h) para descargar el objeto."""
    if not enabled():
        return False, "Storage no configurado"
    base = _base_url()
    try:
        r = httpx.post(
            f"{base}/storage/v1/object/sign/{bucket}/{path}",
            headers=_headers({"Content-Type": "application/json"}),
            json={"expiresIn": expires_in},
            timeout=10,
        )
        if r.status_code != 200:
            return False, f"sign {r.status_code}: {r.text[:200]}"
        data = r.json()
        signed = data.get("signedURL") or data.get("signed_url") or ""
        if not signed:
            return False, "sign: respuesta sin URL"
        # La API devuelve la URL relativa /object/sign/...
        if signed.startswith("/"):
            signed = f"{base}/storage/v1{signed}"
        return True, signed
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def delete(bucket: str, path: str) -> tuple[bool, str]:
    if not enabled():
        return False, "Storage no configurado"
    base = _base_url()
    try:
        r = httpx.delete(
            f"{base}/storage/v1/object/{bucket}/{path}",
            headers=_headers(),
            timeout=10,
        )
        if r.status_code in (200, 204):
            return True, "deleted"
        return False, f"delete {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
