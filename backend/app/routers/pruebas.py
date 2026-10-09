"""Sección PRUEBAS — banco de pruebas para el super admin.

Herramientas para verificar funciones de la plataforma de forma DIRECTA, sin
tocar producción: no procesa cobros, no modifica contratos ni liquidaciones,
no escribe en las tablas de negocio. Todos los endpoints exigen is_superadmin.

Primer item: "Disparo de emails" — manda un email de prueba (con un PDF de
ejemplo) a través del mismo email_service que usan los comprobantes, para
confirmar que el SMTP quedó bien configurado en el entorno.
"""
from __future__ import annotations

import os
import smtplib
import socket
import ssl
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app.services.email_service import enviar_email, smtp_configurado

router = APIRouter(prefix="/api/pruebas", tags=["pruebas"])


def get_superadmin(user=Depends(get_current_user)):
    """Gate: solo el super admin entra a Pruebas."""
    if not getattr(user, "is_superadmin", False):
        raise HTTPException(403, "Solo el super admin puede acceder a Pruebas.")
    return user


def _mask(v: str | None) -> str | None:
    """Enmascara un valor sensible dejando solo pistas (no devuelve secretos)."""
    if not v:
        return None
    v = str(v)
    if "@" in v:  # email → usuario corto + dominio
        nombre, _, dom = v.partition("@")
        return (nombre[:2] + "…@" + dom) if len(nombre) > 2 else ("…@" + dom)
    return v[:2] + "…" if len(v) > 4 else "…"


@router.get("/email/estado")
def email_estado(user=Depends(get_superadmin)):
    """Estado de la config SMTP para la UI (sin exponer la contraseña)."""
    host = os.getenv("SMTP_HOST") or os.getenv("EMAIL_SMTP")
    return {
        "configurado": smtp_configurado(),
        "host": host or None,
        "port": os.getenv("SMTP_PORT", "587"),
        "user": _mask(os.getenv("SMTP_USER")),
        "from": os.getenv("SMTP_FROM") or None,
        "tls": (os.getenv("SMTP_TLS", "true").lower() in ("1", "true", "yes")),
        "tiene_pass": bool(os.getenv("SMTP_PASS")),
    }


@router.get("/email/diagnostico")
def email_diagnostico(user=Depends(get_superadmin)):
    """Prueba el handshake SMTP SIN enviar nada e informa el paso exacto que
    falla. Sirve para distinguir los 3 problemas típicos en producción:
      - faltan variables (config),
      - la credencial es rechazada (auth → revisar App Password),
      - el servidor no puede salir al puerto SMTP (egress bloqueado por el host).
    """
    host = os.getenv("SMTP_HOST") or os.getenv("EMAIL_SMTP")
    port = int(os.getenv("SMTP_PORT", "587") or 587)
    usr = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS", "")
    use_tls = os.getenv("SMTP_TLS", "true").lower() in ("1", "true", "yes")

    def _fin(paso, ok, detalle):
        return {"ok": ok, "paso": paso, "detalle": detalle,
                "host": host or None, "port": port,
                "user": _mask(usr), "tiene_pass": bool(pwd), "tls": use_tls}

    faltan = [n for n, v in (("SMTP_HOST", host), ("SMTP_USER", usr), ("SMTP_PASS", pwd)) if not v]
    if faltan:
        return _fin("config", False, f"Faltan variables en el entorno: {', '.join(faltan)}. "
                    "Cargalas en EasyPanel (servicio de Alquileres) y redeploy.")
    try:
        if port == 465:
            s = smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=12)
        else:
            s = smtplib.SMTP(host, port, timeout=12)
    except (socket.timeout, TimeoutError):
        return _fin("conexion", False, f"No se pudo conectar a {host}:{port} (timeout). "
                    "El servidor de EasyPanel probablemente tiene bloqueada la salida SMTP. "
                    "Habría que habilitar el puerto o usar un proveedor por HTTPS (ej. API de email).")
    except OSError as e:
        return _fin("conexion", False, f"No se pudo conectar a {host}:{port}: {type(e).__name__}: {e}. "
                    "Probable bloqueo de salida SMTP en el host.")
    try:
        with s:
            s.ehlo()
            if port != 465 and use_tls:
                s.starttls(context=ssl.create_default_context())
                s.ehlo()
            try:
                s.login(usr, pwd)
            except smtplib.SMTPAuthenticationError as e:
                return _fin("login", False, "La credencial fue rechazada por el servidor SMTP "
                            f"(código {e.smtp_code}). Revisá SMTP_USER y que SMTP_PASS sea un "
                            "App Password válido de esa cuenta de Gmail (sin espacios).")
    except Exception as e:
        return _fin("handshake", False, f"{type(e).__name__}: {str(e)[:200]}")
    return _fin("login", True, "Conexión y autenticación SMTP OK. El envío debería funcionar.")


class EmailPruebaIn(BaseModel):
    destinatario: str
    con_pdf: bool = True
    copia: str | None = None


# PDF de ejemplo mínimo (válido) para adjuntar en la prueba.
_PDF_DEMO = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 150]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \ntrailer<</Root 1 0 R/Size 4>>\n"
    b"startxref\n0\n%%EOF"
)


@router.post("/email/disparar")
def email_disparar(data: EmailPruebaIn, user=Depends(get_superadmin)):
    """Envía un email de PRUEBA (no toca ningún cobro ni dato de negocio).

    Usa el mismo email_service que los comprobantes de producción, así el
    resultado refleja exactamente si el SMTP del entorno funciona.
    """
    destino = (data.destinatario or "").strip()
    if not destino:
        raise HTTPException(400, "Indicá un email de destino.")
    if not smtp_configurado():
        return {
            "ok": False,
            "mensaje": "SMTP no configurado en este entorno (faltan SMTP_HOST / SMTP_USER).",
        }
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    asunto = "CIUDAD — Prueba de disparo de emails"
    cuerpo = (
        "Este es un email de PRUEBA enviado desde la sección Pruebas de CIUDAD "
        f"({ahora}).\n\nSi lo recibiste, el envío de emails del entorno está "
        "funcionando. No se procesó ningún cobro ni se modificó ningún dato."
    )
    html = (
        "<div style='font-family:system-ui,Segoe UI,Arial,sans-serif;font-size:14px;color:#1a1a1a'>"
        "<h2 style='margin:0 0 8px'>CIUDAD — Prueba de disparo de emails</h2>"
        f"<p style='color:#555'>Enviado el {ahora} desde la sección <b>Pruebas</b>.</p>"
        "<p>Si estás leyendo esto, el <b>SMTP del entorno funciona</b>. "
        "No se procesó ningún cobro ni se modificó ningún dato de producción.</p>"
        "</div>"
    )
    ok, msg = enviar_email(
        destinatario=destino,
        asunto=asunto,
        cuerpo=cuerpo,
        html_body=html,
        pdf_bytes=_PDF_DEMO if data.con_pdf else None,
        pdf_filename="prueba-ciudad.pdf",
        copia=data.copia,
    )
    return {"ok": ok, "mensaje": msg, "destinatario": destino, "con_pdf": bool(data.con_pdf)}
