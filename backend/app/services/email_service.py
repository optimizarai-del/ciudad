"""
Envío de emails con adjuntos PDF.
Configurable vía .env:
  SMTP_HOST=smtp.gmail.com       (acepta EMAIL_SMTP como alias)
  SMTP_PORT=587
  SMTP_USER=tu_usuario           (ej. una cuenta de Gmail — no requiere dominio)
  SMTP_PASS=tu_password          (App Password de Gmail)
  SMTP_FROM=CIUDAD <tu_usuario@gmail.com>
  SMTP_TLS=true
Si SMTP_HOST no está configurado, el envío falla con un mensaje claro
y la función devuelve (False, "razón").
"""
import os
import smtplib
import ssl
from email.message import EmailMessage


def _smtp_host() -> str | None:
    """Host del SMTP. Acepta SMTP_HOST o, como alias, EMAIL_SMTP (que estaba
    en el .env de ejemplo) para no depender de cuál se cargó."""
    return os.getenv("SMTP_HOST") or os.getenv("EMAIL_SMTP")


def _split_emails(v) -> list[str]:
    """Normaliza uno o varios correos: acepta lista, o string separado por
    coma/punto y coma. Descarta vacíos y espacios."""
    if not v:
        return []
    items = v if isinstance(v, (list, tuple)) else str(v).replace(";", ",").split(",")
    return [e.strip() for e in items if e and e.strip()]


def smtp_configurado() -> bool:
    return bool(_smtp_host()) and bool(os.getenv("SMTP_USER"))


def enviar_email(
    destinatario: str,
    asunto: str,
    cuerpo: str,
    pdf_bytes: bytes | None = None,
    pdf_filename: str = "documento.pdf",
    html_body: str | None = None,
    copia=None,
) -> tuple[bool, str]:
    """Devuelve (ok, mensaje). No levanta excepciones.

    `destinatario` puede ser uno o varios correos (separados por coma).
    `copia` (str o lista) manda una copia OCULTA (BCC) a esos correos —
    pensado para que la oficina reciba copia de cada comprobante.
    Si `html_body` viene, el email se envía como multipart con HTML + texto.
    """
    to_list = _split_emails(destinatario)
    bcc_list = _split_emails(copia)
    if not to_list and not bcc_list:
        return False, "Sin destinatario"

    host = _smtp_host()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS", "")
    sender = os.getenv("SMTP_FROM", user or "noreply@ciudad.local")
    use_tls = os.getenv("SMTP_TLS", "true").lower() in ("1", "true", "yes")

    if not host or not user:
        return False, "SMTP no configurado (revisar SMTP_HOST/SMTP_USER en .env)"

    msg = EmailMessage()
    msg["From"] = sender
    if to_list:
        msg["To"] = ", ".join(to_list)
    if bcc_list:
        # send_message lee el header Bcc, lo usa como destinatario y lo quita
        # del mensaje enviado (los demás no ven a quién se copió).
        msg["Bcc"] = ", ".join(bcc_list)
    msg["Subject"] = asunto
    msg.set_content(cuerpo)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

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
