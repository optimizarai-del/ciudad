"""
Email de bienvenida cuando un admin crea un usuario nuevo desde el panel
de Equipo. Le manda al destinatario sus credenciales iniciales y el link
del panel CIUDAD.

Si SMTP no está configurado, no rompe — solo loguea y retorna False.
"""
import os
from app.services.email_service import enviar_email, smtp_configurado


ROL_LABEL = {
    "admin":      "Administrador",
    "gerencia":   "Gerencia",
    "alquileres": "Alquileres",
    "ventas":     "Ventas",
    "agente_ia":  "Agente IA",
}


def _panel_url() -> str:
    return os.getenv("CIUDAD_PANEL_URL", "https://ciudad.optimizar-ia.com")


def enviar_welcome(*, nombre: str, email: str, password: str, role: str) -> tuple[bool, str]:
    """Envía un email HTML de bienvenida con credenciales iniciales."""
    panel = _panel_url()
    rol_legible = ROL_LABEL.get(role, role)

    asunto = "Bienvenido/a a CIUDAD · Tus accesos"

    texto_plano = (
        f"Hola {nombre},\n\n"
        f"Te creamos un acceso al panel de CIUDAD — Negocios Inmobiliarios.\n\n"
        f"  Panel:       {panel}\n"
        f"  Email:       {email}\n"
        f"  Contraseña:  {password}\n"
        f"  Rol:         {rol_legible}\n\n"
        f"Te recomendamos cambiar la contraseña la primera vez que ingreses.\n\n"
        f"#VIVIRMEJOR\n"
        f"— Equipo CIUDAD"
    )

    html = f"""\
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>Bienvenido/a a CIUDAD</title></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#111;">
  <div style="max-width:560px;margin:0 auto;padding:40px 24px;">

    <div style="background:#000;color:#fff;padding:32px 28px;border-radius:24px 24px 0 0;">
      <p style="margin:0;font-size:11px;letter-spacing:2px;color:#999;">NEGOCIOS INMOBILIARIOS</p>
      <h1 style="margin:8px 0 4px;font-size:36px;font-weight:800;letter-spacing:-1px;">CIUDAD.</h1>
      <p style="margin:0;color:#C9A35F;font-size:13px;letter-spacing:1px;">#VIVIRMEJOR</p>
    </div>

    <div style="background:#fff;padding:36px 28px;border-radius:0 0 24px 24px;border:1px solid #eee;border-top:none;">
      <h2 style="margin:0 0 16px;font-size:22px;font-weight:700;letter-spacing:-0.5px;">Hola {nombre}.</h2>
      <p style="margin:0 0 24px;font-size:14px;line-height:1.6;color:#444;">
        Te creamos un acceso al panel de CIUDAD. Con estas credenciales podés ingresar y empezar a operar
        según tu rol asignado:
      </p>

      <div style="background:#fafafa;border:1px solid #eee;border-radius:16px;padding:20px 22px;margin-bottom:24px;">
        <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee;">
          <span style="font-size:12px;color:#777;">Email</span>
          <span style="font-size:13px;font-weight:600;font-family:'SF Mono',Menlo,monospace;">{email}</span>
        </div>
        <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee;">
          <span style="font-size:12px;color:#777;">Contraseña</span>
          <span style="font-size:13px;font-weight:600;font-family:'SF Mono',Menlo,monospace;">{password}</span>
        </div>
        <div style="display:flex;justify-content:space-between;padding:8px 0;">
          <span style="font-size:12px;color:#777;">Rol</span>
          <span style="font-size:13px;font-weight:600;">{rol_legible}</span>
        </div>
      </div>

      <div style="text-align:center;margin:28px 0 8px;">
        <a href="{panel}/login" style="display:inline-block;background:#111;color:#fff;text-decoration:none;padding:14px 32px;border-radius:999px;font-size:13px;font-weight:600;letter-spacing:0.3px;">
          Ingresar al panel
        </a>
      </div>

      <p style="margin:24px 0 0;font-size:12px;color:#999;line-height:1.6;">
        Por seguridad, te recomendamos cambiar la contraseña en tu primer ingreso.
        Si no esperabas este email, contactá al administrador de tu equipo.
      </p>
    </div>

    <p style="text-align:center;font-size:11px;color:#999;margin-top:24px;">
      © CIUDAD — Negocios Inmobiliarios
    </p>
  </div>
</body>
</html>"""

    if not smtp_configurado():
        # No falla — solo avisa al caller. La creación del usuario sigue.
        print(f"[welcome_email] SMTP no configurado. Skip envío a {email}")
        return False, "SMTP no configurado"

    return enviar_email(
        destinatario=email,
        asunto=asunto,
        cuerpo=texto_plano,
        html_body=html,
    )
