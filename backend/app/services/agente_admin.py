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

from app.services.admin_actions import TOOLS


def es_admin(chat_id: str) -> bool:
    raw = os.getenv("TELEGRAM_ADMIN_CHATS", "")
    ids = {s.strip() for s in raw.split(",") if s.strip()}
    return str(chat_id) in ids


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
]


SYSTEM_PROMPT = """Sos el agente administrativo de CIUDAD., una plataforma inmobiliaria.

Hablás con personal del staff por Telegram. Te dan instrucciones en lenguaje natural
para consultar la base o hacer modificaciones masivas. Tu trabajo es:

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
"""


# ────────────────────────────────────────────────────────────────────
# Loop tool-calling con Claude
# ────────────────────────────────────────────────────────────────────

async def responder_admin_llm(texto: str, db: Session) -> str:
    """Devuelve un texto plano listo para enviar por Telegram."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return _responder_comandos(texto, db)

    try:
        from anthropic import Anthropic
    except ImportError:
        return _responder_comandos(texto, db)

    client = Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": texto}]

    for _ in range(6):
        resp = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        if resp.stop_reason == "tool_use":
            # Recoger todas las llamadas a tool del turno
            messages.append({"role": "assistant", "content": resp.content})
            tool_results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                fn = TOOLS.get(block.name)
                if not fn:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"ok": False, "error": f"tool desconocida: {block.name}"}),
                        "is_error": True,
                    })
                    continue
                try:
                    out = fn(db=db, **(block.input or {}))
                except TypeError:
                    out = fn(db, **(block.input or {}))
                except Exception as e:
                    out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(out, default=str)[:8000],
                })
            messages.append({"role": "user", "content": tool_results})
            continue

        # final
        textos = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        return "\n".join(textos).strip() or "Listo."

    return "No pude resolver la solicitud después de varios intentos. Probá con un comando explícito (/buscar, /info, /pendientes…)."


# ────────────────────────────────────────────────────────────────────
# Comandos estructurados (fallback / explícitos)
# ────────────────────────────────────────────────────────────────────

_HELP = (
    "Comandos disponibles:\n"
    "/resumen — vista general\n"
    "/buscar <texto> — busca propiedades\n"
    "/info <id_o_dir> — ficha de una propiedad\n"
    "/contrato <id_o_codigo> — info de contrato\n"
    "/pendientes [YYYY-MM] — pendientes de cobro del mes\n"
    "/actualizar_tasas <ref1>=<monto>; <ref2>=<monto>; ...\n"
    "/actualizar_alquileres <ref1>=<monto>; <ref2>=<monto>; ...\n"
    "/actualizar_expensas <ref1>=<monto>; <ref2>=<monto>; ...\n"
    "/estado <id_o_dir> <disponible|ocupada|reservada|inactiva>\n"
    "\nTambién podés escribir en lenguaje natural si está activado el modelo."
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


def _responder_comandos(texto: str, db: Session) -> str:
    t = texto.strip()
    if not t.startswith("/"):
        return ("No tengo modelo de IA configurado para entender lenguaje natural.\n\n" + _HELP)

    parts = t.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("/start", "/help", "/ayuda"):
        return _HELP

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

    return f"Comando no reconocido: {cmd}\n\n{_HELP}"
