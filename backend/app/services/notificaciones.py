"""
Servicio de notificaciones por email.
Usa smtplib con variables de entorno:
  EMAIL_FROM     — dirección remitente
  EMAIL_PASSWORD — contraseña de la cuenta
  EMAIL_SMTP     — host SMTP (ej: smtp.gmail.com)
  EMAIL_PORT     — puerto (ej: 587)
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional


def _get_smtp_config():
    return {
        "from": os.getenv("EMAIL_FROM", ""),
        "password": os.getenv("EMAIL_PASSWORD", ""),
        "smtp": os.getenv("EMAIL_SMTP", "smtp.gmail.com"),
        "port": int(os.getenv("EMAIL_PORT", "587")),
    }


def _enviar_email(to: str, subject: str, html_body: str) -> bool:
    """Envía un email HTML. Retorna True si tuvo éxito."""
    cfg = _get_smtp_config()
    if not cfg["from"] or not cfg["password"]:
        print(f"[notificaciones] Email no configurado. Destinatario: {to}, Asunto: {subject}")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["from"]
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(cfg["smtp"], cfg["port"]) as server:
            server.starttls()
            server.login(cfg["from"], cfg["password"])
            server.sendmail(cfg["from"], to, msg.as_string())
        return True
    except Exception as e:
        print(f"[notificaciones] Error enviando email: {e}")
        return False


def enviar_recordatorio_vencimiento(contrato, dias_restantes: int) -> bool:
    destinatarios = []
    if contrato.inquilino and contrato.inquilino.email:
        destinatarios.append(contrato.inquilino.email)

    if not destinatarios:
        print(f"[notificaciones] Contrato #{contrato.id} sin destinatario de email.")
        return False

    propiedad = contrato.propiedad.direccion if contrato.propiedad else f"Propiedad #{contrato.propiedad_id}"
    inquilino_nombre = f"{contrato.inquilino.nombre} {contrato.inquilino.apellido or ''}".strip() if contrato.inquilino else "Inquilino"

    if dias_restantes <= 7:
        urgencia = "URGENTE"
    elif dias_restantes <= 30:
        urgencia = "PRÓXIMO"
    else:
        urgencia = "AVISO"

    subject = f"[{urgencia}] Vencimiento de contrato en {dias_restantes} días — {propiedad}"
    html_body = f"""
    <html><body style="font-family: sans-serif; color: #111; max-width: 600px; margin: 0 auto; padding: 24px;">
      <h2 style="border-bottom: 2px solid #000; padding-bottom: 8px;">CIUDAD.</h2>
      <p>Estimado/a <strong>{inquilino_nombre}</strong>,</p>
      <p>Le recordamos que el contrato de alquiler para <strong>{propiedad}</strong>
         vence el <strong>{contrato.fecha_fin.strftime('%d/%m/%Y') if contrato.fecha_fin else 'N/A'}</strong>
         — en <strong>{dias_restantes} días</strong>.</p>
      <p>Por favor, comuníquese con la inmobiliaria para gestionar la renovación o entrega del inmueble.</p>
      <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
      <p style="font-size: 12px; color: #999;">CIUDAD. — Inmuebles · Contratos · Gestión</p>
    </body></html>
    """

    ok = True
    for dest in destinatarios:
        if not _enviar_email(dest, subject, html_body):
            ok = False
    return ok


def enviar_resumen_liquidaciones(liquidaciones: list, mes: str, destinatario: Optional[str] = None) -> bool:
    to = destinatario or os.getenv("EMAIL_FROM", "")
    if not to:
        print("[notificaciones] No hay destinatario para el resumen de liquidaciones.")
        return False

    total_neto = sum(l.get("neto_propietario", 0) for l in liquidaciones)
    pagadas = sum(1 for l in liquidaciones if l.get("estado") == "pagada")
    pendientes = sum(1 for l in liquidaciones if l.get("estado") == "pendiente")

    filas_html = ""
    for liq in liquidaciones:
        estado_color = "#22c55e" if liq.get("estado") == "pagada" else "#f59e0b"
        filas_html += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee;">{liq.get('propiedad','')}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{liq.get('propietario','')}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">${liq.get('neto_propietario',0):,.2f}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;color:{estado_color};font-weight:600;">{liq.get('estado','').upper()}</td>
        </tr>"""

    subject = f"Resumen de liquidaciones — {mes}"
    html_body = f"""
    <html><body style="font-family: sans-serif; color: #111; max-width: 700px; margin: 0 auto; padding: 24px;">
      <h2 style="border-bottom: 2px solid #000; padding-bottom: 8px;">CIUDAD. — Liquidaciones {mes}</h2>
      <table style="width:100%;border-collapse:collapse;">
        <tbody>{filas_html}</tbody>
      </table>
      <p style="font-size:12px;color:#999;">CIUDAD. — Inmuebles · Contratos · Gestión</p>
    </body></html>
    """
    return _enviar_email(to, subject, html_body)
