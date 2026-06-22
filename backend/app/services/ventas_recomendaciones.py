"""
Agente IA de recomendaciones de acciones para el CRM de Ventas.

Dada la ficha 360° de UN cliente (estado de sus pedidos, notas, días sin
contacto, operaciones), propone las próximas acciones concretas y
personalizadas que el vendedor debería tomar.

- Si hay `ANTHROPIC_API_KEY`, usa Claude con response forzado a JSON (tool use)
  → recomendaciones matizadas que leen el contenido de las notas y priorizan.
- Si no hay key o la llamada falla, cae a un motor de reglas determinístico
  (mismo comportamiento histórico) para que el endpoint funcione siempre.

El output siempre es una lista de strings (acciones en imperativo), para no
romper el frontend que renderiza `ficha.recomendaciones` como texto.
"""
import os
import json

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

SYSTEM = """Sos el asistente comercial del CRM de la inmobiliaria CIUDAD. Tu trabajo es \
mirar la ficha de UN cliente y proponer las próximas acciones concretas que el \
vendedor debería tomar para hacer avanzar la relación hacia una operación \
cerrada (o, si ya operó, hacia la fidelización y la recompra).

Contexto del negocio:
- Funnel de pedidos: nuevo → contactado → en_seguimiento → esperando_respuesta \
→ negociando → cerrado/perdido.
- Un cliente puede tener varios pedidos (búsquedas activas) a la vez.
- "es_operado" = ya cerró al menos una compra/venta con nosotros.
- El vendedor carga todo desde el celular; las acciones tienen que ser cortas, \
accionables y específicas de ESTE cliente.

Reglas de salida:
- Devolvé entre 1 y 4 acciones, ordenadas de más a menos urgente.
- Cada acción: un imperativo claro ("Llamar a Juan para coordinar la visita a \
la casa del Centro"), no genérico ("hacer seguimiento").
- Usá los datos reales de la ficha: nombre, zona buscada, presupuesto, días sin \
contacto, contenido de las últimas notas, estado de cada pedido.
- Si hay un pedido en "negociando" o "esperando_respuesta", priorizalo: es lo \
más cerca de cerrar.
- Si pasaron muchos días sin contacto y hay pedidos activos, marcá la urgencia.
- Si el cliente ya operó, incluí una acción de post-venta / recompra.
- No inventes hechos que no estén en la ficha. Si falta info clave (ej. nunca \
se lo contactó), la primera acción es conseguirla.
- Tono: directo, profesional, español rioplatense."""

TOOL = {
    "name": "recomendar_acciones",
    "description": "Devuelve las próximas acciones recomendadas para el cliente.",
    "input_schema": {
        "type": "object",
        "properties": {
            "acciones": {
                "type": "array",
                "minItems": 1,
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "properties": {
                        "texto": {"type": "string", "description": "La acción concreta, en imperativo."},
                        "prioridad": {"type": "string", "enum": ["alta", "media", "baja"]},
                        "motivo": {"type": "string", "description": "Por qué, en una frase corta."},
                    },
                    "required": ["texto", "prioridad"],
                },
            }
        },
        "required": ["acciones"],
    },
}


def _ficha_a_texto(ctx: dict) -> str:
    """Serializa la ficha del cliente al input que recibe el modelo."""
    pedidos = ctx.get("pedidos") or []
    notas = ctx.get("notas") or []
    ped_txt = "\n".join(
        f"    • {p.get('tipo') or 's/tipo'} en {p.get('zona') or 's/zona'} "
        f"[{p.get('estado')}]"
        + (f" hasta USD {p['precio_max']:,}".replace(",", ".") if p.get("precio_max") else "")
        for p in pedidos
    ) or "    (ninguno)"
    notas_txt = "\n".join(
        f"    • {n.get('fecha') or ''}: {n.get('texto')}" for n in notas[:5]
    ) or "    (ninguna)"
    return (
        "Ficha del cliente:\n"
        f"- Nombre: {ctx.get('nombre')}\n"
        f"- ¿Ya operó?: {'sí' if ctx.get('es_operado') else 'no'}\n"
        f"- Días sin contacto: {ctx.get('dias_sin_contacto')}\n"
        f"- Presupuesto máximo buscado: {ctx.get('presupuesto_max') or 's/dato'}\n"
        f"- Operaciones previas: {ctx.get('operaciones', 0)}\n"
        f"- Pedidos activos ({len(pedidos)}):\n{ped_txt}\n"
        f"- Últimas notas ({len(notas)}):\n{notas_txt}\n\n"
        "Proponé las próximas acciones para este cliente."
    )


def _claude(ctx: dict):
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    try:
        import anthropic  # type: ignore
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=SYSTEM,
            tools=[TOOL],
            tool_choice={"type": "tool", "name": "recomendar_acciones"},
            messages=[{"role": "user", "content": _ficha_a_texto(ctx)}],
        )
        for block in msg.content:
            if block.type == "tool_use":
                acciones = (block.input or {}).get("acciones") or []
                textos = [a["texto"].strip() for a in acciones if a.get("texto")]
                return textos or None
    except Exception as e:
        print(f"[ventas_recomendaciones] Claude fallback a reglas: {e}")
    return None


def _reglas(ctx: dict) -> list[str]:
    """Motor determinístico (comportamiento histórico). Fallback sin IA."""
    pedidos = ctx.get("pedidos") or []
    estados = {p.get("estado") for p in pedidos}
    activos = [p for p in pedidos if p.get("estado") not in ("cerrado", "perdido")]
    dias = ctx.get("dias_sin_contacto")
    recs: list[str] = []
    if not ctx.get("notas"):
        recs.append("Registrar el primer contacto y dejar una nota.")
    if "nuevo" in estados:
        recs.append("Contactar al cliente — tiene un pedido sin contactar.")
    if "esperando_respuesta" in estados:
        recs.append("Hacer seguimiento: el cliente está esperando respuesta.")
    if "negociando" in estados:
        recs.append("Avanzar la negociación o registrar una oferta.")
    if "en_seguimiento" in estados:
        recs.append("Continuar el seguimiento periódico.")
    if ctx.get("es_operado"):
        recs.append("Agendar seguimiento post-venta.")
    if dias is not None and dias >= 14 and activos:
        recs.append(f"Pasaron {dias} días sin contacto — conviene retomar.")
    if not recs:
        recs.append("Sin acciones pendientes. Mantené el seguimiento.")
    return recs


def recomendar_acciones(ctx: dict) -> dict:
    """Devuelve {'recomendaciones': [str...], 'motor': 'claude'|'reglas'}."""
    via_ia = _claude(ctx)
    if via_ia:
        return {"recomendaciones": via_ia, "motor": "claude"}
    return {"recomendaciones": _reglas(ctx), "motor": "reglas"}
