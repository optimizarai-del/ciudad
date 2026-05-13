"""
Cliente para consultar la deuda/tasa municipal de Santa Rosa, La Pampa.

Hace de proxy al endpoint oficial:
  POST https://consultadeuda.santarosa.gob.ar/api/deuda

El portal valida un token de reCAPTCHA v2. El token lo resuelve el
frontend del usuario (widget de Google) y lo manda a nuestro backend,
que reenvía la consulta server-to-server (evita CORS).

ENV vars relevantes:
  MSR_RECAPTCHA_SITEKEY  — pegar el sitekey público de la municipalidad
                            (se obtiene haciendo F12 en el portal y
                            mirando el div con data-sitekey de reCAPTCHA).
"""
import os
import re
import httpx
from typing import Optional


PORTAL_URL = "https://consultadeuda.santarosa.gob.ar/api/deuda"


def sitekey() -> Optional[str]:
    return os.getenv("MSR_RECAPTCHA_SITEKEY") or None


async def consultar_deuda(*, padron: str, captcha_token: str,
                          action: str = "getCuenta",
                          ofic99: str = "1",
                          fvto_str: str = "") -> dict:
    """Consulta la deuda de un inmueble por padrón municipal.

    Retorna un dict con:
      ok:       True/False
      error:    str | None
      raw:      la respuesta cruda del municipio (JSON o texto)
      cuotas:   lista de cuotas si pudo parsear
      total:    suma de importes pendientes si pudo parsear

    Args:
      padron: número de referencia / padrón municipal
      captcha_token: token resuelto por el frontend (g-recaptcha-response)
      action: acción del API. 'getCuenta' lista todas las cuotas,
              'getDeudas' devuelve solo las pendientes.
      ofic99: 1=Servicios Municipales, 2=Otros conceptos
      fvto_str: fecha de vencimiento para selección (opcional)
    """
    if not padron:
        return {"ok": False, "error": "Falta numero_referencia en la propiedad"}
    if not captcha_token:
        return {"ok": False, "error": "Falta token de reCAPTCHA"}

    data = {
        "padron": padron.strip(),
        "action": action,
        "captcha": captcha_token,
        "ofic99": ofic99,
        "fvtoStr": fvto_str,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                PORTAL_URL,
                data=data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0 Safari/537.36"
                    ),
                    # El portal valida origen — uso el del propio portal para
                    # no romper la verificación CORS server-side.
                    "Origin": "https://consultadeuda.santarosa.gob.ar",
                    "Referer": "https://consultadeuda.santarosa.gob.ar/",
                },
            )
    except Exception as e:
        return {"ok": False, "error": f"No se pudo conectar con la Municipalidad: {type(e).__name__}: {e}"}

    if r.status_code != 200:
        body = r.text[:500]
        # El portal puede devolver 500 envuelto en JSON con el HTML de
        # error del Tomcat upstream. Lo detectamos para dar un mensaje
        # más amigable.
        if "Apache Tomcat" in body or "ERRORES" in body:
            return {
                "ok": False,
                "error": "El municipio rechazó la consulta (padrón inválido o sistema caído).",
                "raw": body,
            }
        return {"ok": False, "error": f"HTTP {r.status_code}", "raw": body}

    # Parsear respuesta
    try:
        payload = r.json()
    except Exception:
        return {
            "ok": False,
            "error": "Respuesta no parseable como JSON",
            "raw": r.text[:1000],
        }

    # Estructura típica: lista de cuotas con campos id, periodo, importe,
    # vencimiento, etc. Si no es lista, devolvemos crudo.
    if not isinstance(payload, list):
        return {"ok": False, "error": "Formato inesperado", "raw": payload}

    cuotas = []
    total = 0.0
    for item in payload:
        if not isinstance(item, dict):
            continue
        importe = _to_float(
            item.get("importe") or item.get("monto") or item.get("total")
        )
        cuotas.append({
            "id":          item.get("id") or item.get("serializedId"),
            "periodo":     item.get("periodo") or item.get("cuota") or item.get("fecha"),
            "vencimiento": item.get("vencimiento") or item.get("fechaVencimiento"),
            "importe":     importe,
            "estado":      item.get("estado") or item.get("status"),
            "concepto":    item.get("concepto") or item.get("detalle"),
            "_raw":        item,
        })
        if importe:
            total += importe

    return {
        "ok": True,
        "cuotas": cuotas,
        "total": round(total, 2),
        "cantidad": len(cuotas),
        "raw": payload,
    }


def _to_float(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    # Normalizar formato $1.234,56 → 1234.56
    s = re.sub(r"[^0-9,.\-]", "", s)
    if s.count(",") == 1 and (s.rfind(",") > s.rfind(".")):
        # formato AR: punto miles, coma decimal
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return 0.0
