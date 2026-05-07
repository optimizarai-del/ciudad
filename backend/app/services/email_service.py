"""
Envío de emails con adjuntos PDF.
Configurable vía .env:
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=tu_usuario
  SMTP_PASS=tu_password
  SMTP_FROM=CIUDAD. <noreply@ciudad.com>
  SMTP_TLS=true
Si SMTP_HOST no está configurado, el envío falla con un mensaje claro
y la función devuelve (False, "razón").
"""
import os
import smtplib
import ssl
from email.message import EmailMessage


def smtp_configurado() -> bool:
    return bool(os.getenv("SMTP_HOST")) and bool(os.getenv("SMTP_USER"))


def enviar_email(
    destinatario: str,
    asunto: str,
    cuerpo: str,
    pdf_bytes: bytes | None = None,
    pdf_filename: str = "documento.pdf",
) -> tuple[bool, str]:
    """Devuelve (ok, mensaje). No levanta excepciones."""
    if not destinatario:
        return False, "Sin destinatario"

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS", "")
    sender = os.getenv("SMTP_FROM", user or "noreply@ciudad.local")
    use_tls = os.getenv("SMTP_TLS", "true").lower() in ("1", "true", "yes")

    if not host or not user:
        return False, "SMTP no configurado (revisar SMTP_HOST/SMTP_USER en .env)"

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.set_content(cuerpo)

    if pdf_bytes:
        msg.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename=pdf_filename,
        )

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=15) as s:
                s.login(user, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as s:
                s.ehlo()
                if use_tls:
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
                s.login(user, password)
                s.send_message(msg)
        return True, "Enviado"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
