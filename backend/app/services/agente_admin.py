"""
Agente administrativo de Telegram.

Recibe mensajes de chats que están en la whitelist (TELEGRAM_ADMIN_CHATS) y
ejecuta acciones contra la base. Tiene dos vías:

  1. Tool-calling con Claude — si hay ANTHROPIC_API_KEY configurada, el modelo
     decide qué herramientas invocar y resume el resultado. Permite
     instrucciones en lenguaje natural y operaciones masivas como:
       "actualizá las tasas municipales: Av. Corrientes 1234 a 45000,
        Bolívar 555 a 32000"
     Claude llama actualizar_tasas_municipales con el listado parseado.

  2. Comandos estructurados — como fallback (sin API key) o cuando el usuario
     prefiere ser explícito:
       /buscar <texto>
       /info <id_o_direccion>
       /pendientes [YYYY-MM]
       /resumen
       /actualizar_tasas Direccion 1 = 12345 ; Direccion 2 = 6789
       /actualizar_alquileres ...
"""
import json
import os
import re
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.services.admin_actions import TOOLS


# Permisos por rol — qué tools puede invocar cada uno desde Telegram.
ROLE_TOOLS = {
    "admin":      set(TOOLS.keys()),
    "gerencia":   set(TOOLS.keys()),
    "alquileres": {
        "buscar_propiedad", "info_propiedad", "info_contrato",
        "listar_pendientes_cobro", "resumen_dashboard",
        "actualizar_tasas_municipales", "actualizar_alquileres",
        "actualizar_expensas", "cambiar_estado_propiedad",
        "calcular_alquiler", "crear_evento",
    },
    "ventas": {
        "buscar_propiedad", "info_propiedad", "info_contrato",
        "resumen_dashboard", "calcular_alquiler", "crear_evento",
        # Tokko = corazón del área de Ventas
        "tokko_buscar_red", "tokko_ficha", "tokko_estadisticas_zona",
        "tokko_comparables",
    },
    "agente_ia": {
        "buscar_propiedad", "info_propiedad", "info_contrato",
        "resumen_dashboard", "calcular_alquiler",
        # El agente puede consultar la red Tokko para responder a leads
        "tokko_buscar_red", "tokko_ficha", "tokko_estadisticas_zona",
        "tokko_comparables",
    },
}


def autorizar(chat_id: str, db: Session) -> Optional[dict]:
    """
    Devuelve {role, user_id, nombre} si el chat está autorizado, None si no.

    Orden:
      1. User.telegram_chat_id == chat_id en BD → rol del usuario.
      2. chat_id en TELEGRAM_ADMIN_CHATS → rol "admin" (dev / fallback).
    """
    chat_id = str(chat_id)
    u = db.query(models.User).filter_by(telegram_chat_id=chat_id, is_active=True).first()
    if u:
        return {
            "role": u.role.value if hasattr(u.role, "value") else u.role,
            "user_id": u.id,
            "nombre": u.nombre,
        }
    raw = os.getenv("TELEGRAM_ADMIN_CHATS", "")
    if chat_id in {s.strip() for s in raw.split(",") if s.strip()}:
        return {"role": "admin", "user_id": None, "nombre": "Admin (env)"}
    return None


def es_admin(chat_id: str, db: Optional[Session] = None) -> bool:
    """Compat: True si el chat está autorizado con cualquier rol."""
    if db is not None:
        return autorizar(chat_id, db) is not None
    raw = os.getenv("TELEGRAM_ADMIN_CHATS", "")
    return str(chat_id) in {s.strip() for s in raw.split(",") if s.strip()}


def tools_permitidos(role: str) -> set[str]:
    return ROLE_TOOLS.get(role, set())


# ────────────────────────────────────────────────────────────────────
# Esquemas de tools para Claude (formato Anthropic)
# ────────────────────────────────────────────────────────────────────

TOOL_SCHEMAS = [
    {
        "name": "buscar_propiedad",
        "description": "Busca propiedades por dirección, código, ciudad o tokko_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Texto de búsqueda"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "info_propiedad",
        "description": "Devuelve la ficha completa de una propiedad (datos + propietario + contrato vigente).",
        "input_schema": {
            "type": "object",
            "properties": {
                "identificador": {"type": "string", "description": "id, código o substring de dirección"},
            },
            "required": ["identificador"],
        },
    },
    {
        "name": "info_contrato",
        "description": "Información de un contrato (por id o código).",
        "input_schema": {
            "type": "object",
            "properties": {"identificador": {"type": "string"}},
            "required": ["identificador"],
        },
    },
    {
        "name": "listar_pendientes_cobro",
        "description": "Lista los contratos vigentes con cobro pendiente para el mes indicado.",
        "input_schema": {
            "type": "object",
            "properties": {"mes": {"type": "string", "description": "YYYY-MM (opcional, default mes actual)"}},
        },
    },
    {
        "name": "resumen_dashboard",
        "description": "Resumen ejecutivo: propiedades totales, ocupadas, disponibles, contratos vigentes, leads nuevos.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "actualizar_tasas_municipales",
        "description": (
            "Actualiza en masa el campo tasas_municipales (ABL + alumbrado + inmobiliario unificados). "
            "Recibe una lista de actualizaciones."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "propiedad": {"type": "string", "description": "id, código o dirección"},
                            "monto": {"type": "number"},
                        },
                        "required": ["propiedad", "monto"],
                    },
                }
            },
            "required": ["updates"],
        },
    },
    {
        "name": "actualizar_alquileres",
        "description": "Actualiza en masa el precio_alquiler de una lista de propiedades.",
        "input_schema": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "propiedad": {"type": "string"},
                            "monto": {"type": "number"},
                        },
                        "required": ["propiedad", "monto"],
                    },
                }
            },
            "required": ["updates"],
        },
    },
    {
        "name": "actualizar_expensas",
        "description": "Actualiza en masa el campo expensas de una lista de propiedades.",
        "input_schema": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "propiedad": {"type": "string"},
                            "monto": {"type": "number"},
                        },
                        "required": ["propiedad", "monto"],
                    },
                }
            },
            "required": ["updates"],
        },
    },
    {
        "name": "cambiar_estado_propiedad",
        "description": "Cambia el estado de una propiedad (disponible/ocupada/reservada/inactiva).",
        "input_schema": {
            "type": "object",
            "properties": {
                "identificador": {"type": "string"},
                "nuevo_estado": {"type": "string", "enum": ["disponible", "ocupada", "reservada", "inactiva"]},
            },
            "required": ["identificador", "nuevo_estado"],
        },
    },
    {
        "name": "calcular_alquiler",
        "description": (
            "Calcula el alquiler actualizado de una propiedad a una fecha dada. "
            "Aplica el ajuste del contrato vigente con índices reales (IPC/ICL) "
            "y suma expensas + tasas municipales."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identificador": {"type": "string", "description": "id, código o dirección"},
                "fecha": {"type": "string", "description": "YYYY-MM-DD (opcional, default hoy)"},
            },
            "required": ["identificador"],
        },
    },
    {
        "name": "crear_evento",
        "description": (
            "Crea un evento/nota en el activity log de Ciudad (recordatorio, "
            "vencimiento, observación). Útil para que el staff registre algo "
            "desde Telegram."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string"},
                "descripcion": {"type": "string"},
                "tipo": {"type": "string", "enum": ["alta", "pago", "ajuste", "vencimiento", "nota", "consulta_ia"]},
                "propiedad_id": {"type": "integer"},
                "contrato_id": {"type": "integer"},
                "es_critico": {"type": "boolean"},
            },
            "required": ["titulo"],
        },
    },
    # ── Tokko: análisis de mercado ───────────────────────────────────────
    {
        "name": "tokko_buscar_red",
        "description": (
            "Busca propiedades en la red de Tokko Broker con filtros. "
            "Permite ver propiedades que ofrecen otras inmobiliarias afiliadas "
            "(no solo las de tu cuenta). Útil para encontrar comparables, "
            "ver oferta disponible en una zona o calcular precios de mercado."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "operacion": {"type": "string", "enum": ["venta", "alquiler", "alquiler_temporal"], "default": "venta"},
                "tipo": {"type": "string", "description": "Casa, Departamento, Local, Terreno, Campo, etc."},
                "ciudad": {"type": "string", "description": "Filtra por nombre de ciudad/zona (substring)"},
                "dormitorios_min": {"type": "integer"},
                "precio_min": {"type": "number"},
                "precio_max": {"type": "number"},
                "moneda": {"type": "string", "enum": ["USD", "ARS"], "default": "USD"},
                "limit": {"type": "integer", "default": 20, "maximum": 50},
            },
        },
    },
    {
        "name": "tokko_ficha",
        "description": "Devuelve la ficha completa de una propiedad de la red Tokko por su id Tokko.",
        "input_schema": {
            "type": "object",
            "properties": {"tokko_id": {"type": "string"}},
            "required": ["tokko_id"],
        },
    },
    {
        "name": "tokko_estadisticas_zona",
        "description": (
            "Estadísticas de mercado de Tokko: precio promedio/mediana/min/max y "
            "precio por m² para una combinación operación+tipo+ciudad. Útil para "
            "valuar una propiedad o hacer un análisis de mercado para un cliente."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "operacion": {"type": "string", "enum": ["venta", "alquiler"], "default": "venta"},
                "tipo": {"type": "string"},
                "ciudad": {"type": "string"},
                "moneda": {"type": "string", "enum": ["USD", "ARS"], "default": "USD"},
                "sample": {"type": "integer", "default": 50, "maximum": 50},
            },
        },
    },
    {
        "name": "tokko_comparables",
        "description": (
            "Dada una propiedad local de CIUDAD por id, busca comparables en la "
            "red Tokko (mismo tipo, ciudad, ±tolerancia de m²) y devuelve "
            "estadísticas de precios para sugerir valuación competitiva."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "propiedad_id": {"type": "integer"},
                "operacion": {"type": "string", "enum": ["venta", "alquiler"], "default": "venta"},
                "tolerancia_m2": {"type": "integer", "default": 30},
            },
            "required": ["propiedad_id"],
        },
    },
]


SYSTEM_PROMPT_BASE = """Sos el agente administrativo de CIUDAD — Negocios Inmobiliarios.

Hablás con personal del staff por Telegram. Te dan instrucciones en lenguaje natural
para consultar la base o hacer modificaciones. Tu trabajo es:

1. Entender la intención.
2. Llamar a una o más herramientas para resolverla.
3. Confirmar el resultado en español rioplatense, en mensajes BREVES y claros para
   leer en Telegram (sin markdown pesado, máximo ~10 líneas, listas con guiones).

Reglas:
- Cuando te pidan actualizaciones masivas (varias propiedades), parseá la lista y
  pasala completa a la tool en una sola llamada.
- Si una propiedad está ambigua, pedí aclaración en vez de adivinar.
- Las "tasas municipales" agrupan ABL + alumbrado + inmobiliario en un solo monto.
- Después de actualizar, indicá cuántas se actualizaron, cuántas fallaron y por qué.
- No inventes propiedades. Si no aparecen en los resultados, decilo.
- Si el usuario pide algo fuera de tus permisos, explicale brevemente que no podés
  ejecutarlo y sugerí qué sí podés hacer.
"""


# ────────────────────────────────────────────────────────────────────
# Loop tool-calling con Claude
# ────────────────────────────────────────────────────────────────────

async def responder_admin_llm(texto: str, db: Session, role: str = "admin", nombre: str = "") -> str:
    """
    Devuelve un texto plano listo para enviar por Telegram.
    `role` filtra qué tools puede invocar el modelo.
    """
    permitidos = tools_permitidos(role)
    if not permitidos:
        return f"⚠ Tu rol ({role}) no tiene tools habilitadas en el agente admin."

    schemas = [t for t in TOOL_SCHEMAS if t["name"] in permitidos]
    system = SYSTEM_PROMPT_BASE + (
        f"\n\nUsuario: {nombre or 'Staff'} (rol: {role}). "
        f"Tools habilitadas: {', '.join(sorted(permitidos))}."
    )

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return _responder_comandos(texto, db, permitidos)

    try:
        from anthropic import Anthropic
    except ImportError:
        return _responder_comandos(texto, db, permitidos)

    client = Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": texto}]

    for _ in range(6):
        resp = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=1500,
            system=system,
            tools=schemas,
            messages=messages,
        )

        if resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})
            tool_results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                # Doble protección: aunque sólo le mandamos los schemas
                # permitidos, validamos también acá.
                if block.name not in permitidos:
                    out = {"ok": False, "error": f"acción no permitida para tu rol ({role})"}
                else:
                    fn = TOOLS.get(block.name)
                    try:
                        out = fn(db=db, **(block.input or {})) if fn else {"ok": False, "error": "tool desconocida"}
                    except TypeError:
                        out = fn(db, **(block.input or {})) if fn else {"ok": False, "error": "tool desconocida"}
                    except Exception as e:
                        out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(out, default=str)[:8000],
                })
            messages.append({"role": "user", "content": tool_results})
            continue

        textos = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        return "\n".join(textos).strip() or "Listo."

    return "No pude resolver la solicitud después de varios intentos. Probá con un comando explícito (/buscar, /info, /pendientes…)."


# ────────────────────────────────────────────────────────────────────
# Comandos estructurados (fallback / explícitos)
# ────────────────────────────────────────────────────────────────────

_HELP = (
    "Comandos disponibles (los permisos dependen de tu rol):\n"
    "Consulta:\n"
    "  /resumen — vista general\n"
    "  /buscar <texto> — busca propiedades\n"
    "  /info <id_o_dir> — ficha de una propiedad\n"
    "  /contrato <id_o_codigo> — info de contrato\n"
    "  /pendientes [YYYY-MM] — pendientes de cobro del mes\n"
    "  /calcular <id_o_dir> [YYYY-MM-DD] — alquiler actualizado\n"
    "Modificación masiva:\n"
    "  /actualizar_tasas <ref>=<monto>; ...\n"
    "  /actualizar_alquileres <ref>=<monto>; ...\n"
    "  /actualizar_expensas <ref>=<monto>; ...\n"
    "  /estado <id_o_dir> <disponible|ocupada|reservada|inactiva>\n"
    "  /evento <título> [| descripción]\n"
    "\nTambién podés escribir en lenguaje natural si hay modelo configurado."
)


def _parse_lista(arg: str) -> list[dict]:
    items = []
    for chunk in re.split(r"[;\n]", arg):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" in chunk:
            ref, monto = chunk.split("=", 1)
        elif ":" in chunk:
            ref, monto = chunk.split(":", 1)
        else:
            partes = chunk.rsplit(" ", 1)
            if len(partes) != 2:
                continue
            ref, monto = partes
        ref = ref.strip()
        # quitar separadores y símbolos del monto: $, ., separadores miles
        m = re.sub(r"[^\d,.\-]", "", monto)
        m = m.replace(".", "").replace(",", ".") if m.count(",") and m.count(".") <= 1 else m.replace(",", "")
        try:
            monto_f = float(m)
        except ValueError:
            continue
        items.append({"propiedad": ref, "monto": monto_f})
    return items


def _format_resumen(d: dict) -> str:
    return (
        f"Resumen CIUDAD.\n"
        f"- Propiedades: {d['propiedades_total']} ({d['propiedades_disponibles']} disp · {d['propiedades_ocupadas']} ocup)\n"
        f"- Contratos vigentes: {d['contratos_vigentes']}\n"
        f"- Clientes: {d['clientes_total']} (propietarios: {d['propietarios']})\n"
        f"- Leads nuevos: {d['leads_nuevos']}"
    )


def _format_busqueda(d: dict) -> str:
    if not d.get("ok"):
        return f"⚠ {d.get('error')}"
    if d["total"] == 0:
        return "Sin resultados."
    out = [f"Resultados ({d['total']}):"]
    for p in d["propiedades"]:
        out.append(f"- #{p['id']} {p['direccion']} · {p['ciudad']} · ${int(p['precio_alquiler']):,}")
    return "\n".join(out)


def _format_info(d: dict) -> str:
    if not d.get("ok"):
        return f"⚠ {d['error']}"
    p = d["propiedad"]
    out = [f"#{p['id']} {p['direccion']}",
           f"  {p['tipo']} · {p['modalidad']} · {p['estado']}",
           f"  Alquiler: ${int(p['precio_alquiler']):,}",
           f"  Expensas: ${int(p['expensas']):,}",
           f"  Tasas munic.: ${int(p['tasas_municipales']):,}"]
    if d.get("propietario"):
        pr = d["propietario"]
        out.append(f"  Propietario: {pr['nombre']} ({pr.get('email') or 's/email'})")
    if d.get("contrato_vigente"):
        c = d["contrato_vigente"]
        out.append(f"  Contrato {c['codigo']}: ${int(c['monto_inicial'] or 0):,}")
    return "\n".join(out)


def _format_pendientes(d: dict) -> str:
    if not d.get("ok"):
        return f"⚠ {d['error']}"
    out = [f"Pendientes {d['mes']} ({d['total_pendientes']} contratos · ${int(d['monto_total_pendiente']):,})"]
    for it in d["items"][:15]:
        out.append(f"- {it['contrato_codigo']} · {it['propiedad']} · ${int(it['monto']):,}")
    if len(d["items"]) > 15:
        out.append(f"… y {len(d['items']) - 15} más")
    return "\n".join(out)


def _format_bulk(d: dict, etiqueta: str) -> str:
    if not d.get("ok"):
        return f"⚠ {d.get('error')}"
    out = [f"{etiqueta} actualizadas: {d['actualizadas']} ✓ / {d['fallidas']} ✗"]
    for it in d.get("items", [])[:10]:
        out.append(f"- {it['direccion']}: ${int(it['anterior']):,} → ${int(it['nuevo']):,}")
    if d.get("errores"):
        out.append("Errores:")
        for e in d["errores"][:5]:
            out.append(f"  · {e['input']}: {e['razon']}")
    return "\n".join(out)


CMD_TO_TOOL = {
    "/resumen":               "resumen_dashboard",
    "/buscar":                "buscar_propiedad",
    "/buscar_propiedad":      "buscar_propiedad",
    "/info":                  "info_propiedad",
    "/contrato":              "info_contrato",
    "/pendientes":            "listar_pendientes_cobro",
    "/actualizar_tasas":      "actualizar_tasas_municipales",
    "/tasas":                 "actualizar_tasas_municipales",
    "/actualizar_alquileres": "actualizar_alquileres",
    "/alquileres":            "actualizar_alquileres",
    "/actualizar_expensas":   "actualizar_expensas",
    "/expensas":              "actualizar_expensas",
    "/estado":                "cambiar_estado_propiedad",
    "/calcular":              "calcular_alquiler",
    "/evento":                "crear_evento",
}


def _responder_comandos(texto: str, db: Session, permitidos: Optional[set[str]] = None) -> str:
    """Procesa comandos /. Si `permitidos` está dado, niega los que no estén."""
    t = texto.strip()
    if not t.startswith("/"):
        return ("No tengo modelo de IA configurado para entender lenguaje natural.\n\n" + _HELP)

    parts = t.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("/start", "/help", "/ayuda"):
        return _HELP

    # Verificación de permisos para los comandos que mapean a tools.
    needed = CMD_TO_TOOL.get(cmd)
    if permitidos is not None and needed and needed not in permitidos:
        return f"⚠ Tu rol no tiene permiso para `{cmd}`. Probá comandos de consulta como /buscar o /info."

    if cmd == "/resumen":
        return _format_resumen(TOOLS["resumen_dashboard"](db))

    if cmd in ("/buscar", "/buscar_propiedad"):
        if not arg:
            return "Uso: /buscar <texto>"
        return _format_busqueda(TOOLS["buscar_propiedad"](db, arg))

    if cmd == "/info":
        if not arg:
            return "Uso: /info <id_o_direccion>"
        return _format_info(TOOLS["info_propiedad"](db, arg))

    if cmd == "/contrato":
        if not arg:
            return "Uso: /contrato <id_o_codigo>"
        out = TOOLS["info_contrato"](db, arg)
        if not out.get("ok"):
            return f"⚠ {out['error']}"
        c = out["contrato"]
        return (f"Contrato {c['codigo']} · {c['estado']} · {c['tipo']}\n"
                f"  Propiedad: {c.get('propiedad') or '—'}\n"
                f"  Inquilino: {c.get('inquilino') or '—'}\n"
                f"  Monto: ${int(c['monto_inicial'] or 0):,}\n"
                f"  Comisión: {c.get('comision_porc') or 0}%")

    if cmd == "/pendientes":
        return _format_pendientes(TOOLS["listar_pendientes_cobro"](db, arg or None))

    if cmd in ("/actualizar_tasas", "/tasas"):
        ups = _parse_lista(arg)
        if not ups:
            return ("Uso: /actualizar_tasas Direccion=monto; Direccion=monto; ...\n"
                    "Ejemplo: /actualizar_tasas Av. Corrientes 1234 = 45000; Bolívar 555 = 32000")
        return _format_bulk(TOOLS["actualizar_tasas_municipales"](db, ups), "Tasas")

    if cmd in ("/actualizar_alquileres", "/alquileres"):
        ups = _parse_lista(arg)
        if not ups:
            return "Uso: /actualizar_alquileres Direccion=monto; Direccion=monto; ..."
        return _format_bulk(TOOLS["actualizar_alquileres"](db, ups), "Alquileres")

    if cmd in ("/actualizar_expensas", "/expensas"):
        ups = _parse_lista(arg)
        if not ups:
            return "Uso: /actualizar_expensas Direccion=monto; Direccion=monto; ..."
        return _format_bulk(TOOLS["actualizar_expensas"](db, ups), "Expensas")

    if cmd == "/estado":
        m = re.match(r"^(.*?)\s+(\w+)\s*$", arg)
        if not m:
            return "Uso: /estado <id_o_direccion> <disponible|ocupada|reservada|inactiva>"
        ref, est = m.group(1).strip(), m.group(2).strip().lower()
        out = TOOLS["cambiar_estado_propiedad"](db, ref, est)
        if not out.get("ok"):
            return f"⚠ {out['error']}"
        return f"Estado cambiado: {out['direccion']} → {out['nuevo']}"

    if cmd == "/calcular":
        if not arg:
            return "Uso: /calcular <id_o_direccion> [YYYY-MM-DD]"
        partes = arg.rsplit(" ", 1)
        ref = arg
        fecha = None
        # Si lo último parece YYYY-MM-DD, lo tomamos como fecha
        if len(partes) == 2 and re.match(r"^\d{4}-\d{2}-\d{2}$", partes[1]):
            ref, fecha = partes[0].strip(), partes[1]
        out = TOOLS["calcular_alquiler"](db, ref, fecha)
        if not out.get("ok"):
            return f"⚠ {out.get('error')}"
        prop = out.get("propiedad") or {}
        return (
            f"Cálculo {prop.get('direccion','—')}\n"
            f"  Base: ${int(out.get('base_alquiler') or 0):,}\n"
            f"  Factor: {out.get('factor_ajuste')}\n"
            f"  Alquiler ajustado: ${int(out.get('alquiler_actualizado') or 0):,}\n"
            f"  Total mensual: ${int(out.get('total_mensual') or 0):,}"
        )

    if cmd == "/evento":
        if not arg:
            return "Uso: /evento <título> [| descripción]"
        if "|" in arg:
            titulo, descripcion = [s.strip() for s in arg.split("|", 1)]
        else:
            titulo, descripcion = arg.strip(), None
        out = TOOLS["crear_evento"](db, titulo, descripcion)
        if not out.get("ok"):
            return f"⚠ {out.get('error')}"
        return f"Evento creado #{out['id']}: {out['titulo']}"

    return f"Comando no reconocido: {cmd}\n\n{_HELP}"
