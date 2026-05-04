"""
Servicio del Agente IA de Ciudad.
- Debounce en memoria (reemplaza Redis del flujo n8n)
- Claude Sonnet via Anthropic SDK con tool_use
- Tools: consultar_alquileres, consultar_ventas, consultar_campos → SQLite local
- CRM automático: crea/actualiza leads en la DB
- Split de respuesta en oraciones para envío natural
"""
import asyncio
import re
import json
import os
from datetime import datetime
from typing import Optional
import anthropic
from sqlalchemy.orm import Session
from app import models

# ── Debounce ─────────────────────────────────────────────────────────────────
_buffers: dict[str, list[str]] = {}
_timers: dict[str, asyncio.TimerHandle] = {}
_callbacks: dict[str, asyncio.Future] = {}

async def debounce_message(canal_id: str, texto: str, delay: float = 20.0) -> str:
    """Acumula mensajes de la misma conversación por `delay` segundos."""
    loop = asyncio.get_event_loop()
    if canal_id not in _buffers:
        _buffers[canal_id] = []
    _buffers[canal_id].append(texto)

    # Cancelar timer previo
    if canal_id in _timers:
        _timers[canal_id].cancel()
    if canal_id not in _callbacks or _callbacks[canal_id].done():
        _callbacks[canal_id] = loop.create_future()

    def _fire():
        msgs = _buffers.pop(canal_id, [])
        _timers.pop(canal_id, None)
        fut = _callbacks.get(canal_id)
        if fut and not fut.done():
            fut.set_result(" ".join(msgs))

    _timers[canal_id] = loop.call_later(delay, _fire)
    return await _callbacks[canal_id]


# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """# ROL E IDENTIDAD
Eres el Asistente Virtual de Ciudad Negocios Inmobiliarios (La Pampa).
Trayectoria desde 1996. Tono: Profesional, pampeano (cordial pero directo), confiable.
Prohibido identificarte como IA.

# OBJETIVO PRINCIPAL
Completar la Ficha de Interés para derivar al asesor humano. No cierras ventas, calificas leads.

# FICHA DE INTERÉS
1. OPERACIÓN: Venta / Alquiler
2. TIPO: Casa, Depto, Terreno, Local, Campo
3. UBICACIÓN: Barrio (Santa Rosa/Toay) o zona rural
4. URGENCIA: ¿Busca para ahora o inversión?
5. PRESUPUESTO: Monto y moneda

# FLUJO OBLIGATORIO (orden estricto, UNA pregunta por mensaje)

## A. ALQUILERES/VENTAS URBANOS
Pregunta 1: "¿Dónde estás buscando? ¿Santa Rosa o Toay?"
Pregunta 2: "¿Qué zona preferís? ¿Centro, afueras o algún barrio particular?"
Pregunta 3: "¿Cuántas habitaciones necesitás?"
→ Recién después usar tool consultar_propiedades

## B. CAMPOS
Pregunta 1: "¿Qué cantidad de hectáreas buscás aproximadamente?"
Pregunta 2: "¿En qué zona o ruta buscás el campo?"
→ Recién después usar tool consultar_propiedades

## C. VENDEDORES
Preguntas: tipo → ubicación → dormitorios+superficie → mejoras → precio → nombre+telefono

# REGLA CRÍTICA
NO consultes la base de datos hasta tener TODOS los datos mínimos.
Solo UNA pregunta por mensaje.

# FORMATO DE SALIDA (JSON ÚNICO, sin markdown)
{
  "respuesta": "Tu mensaje al usuario.",
  "comando": "crear" | "actualizar" | "estado" | "nada",
  "mensaje_comando": "Nota para el CRM."
}

## LÓGICA DE COMANDOS
- crear: Primera interacción del usuario
- actualizar: Agregó/modificó datos
- estado: Cambiar estado del lead (interesado / a_contactar / descartado)
- nada: Conversación en curso sin acción CRM
"""

# ── Tools definition ──────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "consultar_propiedades",
        "description": "Consulta la base de datos de propiedades de Ciudad. Úsala SOLO después de tener los datos mínimos del usuario.",
        "input_schema": {
            "type": "object",
            "properties": {
                "modalidad": {
                    "type": "string",
                    "enum": ["alquiler", "venta", "campo"],
                    "description": "Tipo de operación"
                },
                "tipo": {
                    "type": "string",
                    "description": "departamento, casa, local, campo"
                },
                "zona": {
                    "type": "string",
                    "description": "Zona o barrio buscado"
                },
                "habitaciones": {
                    "type": "integer",
                    "description": "Número de habitaciones (opcional)"
                },
                "hectareas_min": {
                    "type": "number",
                    "description": "Para campos: hectáreas mínimas"
                },
                "hectareas_max": {
                    "type": "number",
                    "description": "Para campos: hectáreas máximas"
                }
            },
            "required": ["modalidad"]
        }
    }
]

def _ejecutar_tool(tool_name: str, tool_input: dict, db: Session) -> str:
    """Ejecuta el tool de consulta de propiedades contra la DB de Ciudad."""
    if tool_name != "consultar_propiedades":
        return json.dumps({"error": "Tool desconocido"})

    query = db.query(models.Propiedad)

    modalidad = tool_input.get("modalidad", "")
    if modalidad == "campo":
        query = query.filter(models.Propiedad.tipo == models.PropiedadTipo.campo)
    elif modalidad == "alquiler":
        query = query.filter(
            models.Propiedad.modalidad.in_([
                models.PropiedadModalidad.alquiler,
                models.PropiedadModalidad.ambas
            ])
        )
    elif modalidad == "venta":
        query = query.filter(
            models.Propiedad.modalidad.in_([
                models.PropiedadModalidad.venta,
                models.PropiedadModalidad.ambas
            ])
        )

    tipo = tool_input.get("tipo", "")
    if tipo and modalidad != "campo":
        tipo_map = {
            "depto": models.PropiedadTipo.departamento,
            "departamento": models.PropiedadTipo.departamento,
            "casa": models.PropiedadTipo.casa,
            "local": models.PropiedadTipo.local,
        }
        tipo_modelo = tipo_map.get(tipo.lower())
        if tipo_modelo:
            query = query.filter(models.Propiedad.tipo == tipo_modelo)

    habitaciones = tool_input.get("habitaciones")
    if habitaciones:
        query = query.filter(models.Propiedad.ambientes >= habitaciones)

    ha_min = tool_input.get("hectareas_min")
    ha_max = tool_input.get("hectareas_max")
    if ha_min:
        query = query.filter(models.Propiedad.superficie_m2 >= ha_min * 10000)
    if ha_max:
        query = query.filter(models.Propiedad.superficie_m2 <= ha_max * 10000)

    query = query.filter(models.Propiedad.estado == models.PropiedadEstado.disponible)
    propiedades = query.limit(5).all()

    if not propiedades:
        return json.dumps({
            "resultados": 0,
            "mensaje": "No hay propiedades disponibles con esas características en este momento."
        })

    results = []
    for p in propiedades:
        precio = ""
        if modalidad == "alquiler" and p.precio_alquiler:
            precio = f"${p.precio_alquiler:,.0f}/mes"
            if p.expensas:
                precio += f" + ${p.expensas:,.0f} expensas"
        elif modalidad == "venta" and p.precio_venta:
            precio = f"USD {p.precio_venta:,.0f}"
        elif modalidad == "campo" and p.precio_venta:
            precio = f"USD {p.precio_venta:,.0f}"

        results.append({
            "codigo": p.codigo,
            "direccion": p.direccion,
            "ciudad": p.ciudad,
            "tipo": p.tipo.value if p.tipo else "",
            "ambientes": p.ambientes,
            "superficie": f"{p.superficie_m2:.0f}m²" if p.superficie_m2 else "",
            "precio": precio or "A consultar",
            "descripcion": (p.descripcion or "")[:120]
        })

    return json.dumps({"resultados": len(results), "propiedades": results}, ensure_ascii=False)


# ── CRM actions ───────────────────────────────────────────────────────────────
def _aplicar_crm(comando: str, mensaje_cmd: str, canal_id: str, canal: str, db: Session) -> models.Lead:
    lead = db.query(models.Lead).filter_by(canal_id=canal_id).first()

    if not lead:
        lead = models.Lead(
            canal=canal,
            canal_id=canal_id,
        )
        db.add(lead)

    lead.notas_crm = (lead.notas_crm or "") + f"\n[{datetime.now().strftime('%d/%m %H:%M')}] {mensaje_cmd}"
    lead.ultima_actividad = datetime.utcnow()

    if comando == "estado":
        msg_lower = mensaje_cmd.lower()
        if "a_contactar" in msg_lower or "contactar" in msg_lower:
            lead.estado = models.LeadEstado.a_contactar
        elif "interesado" in msg_lower:
            lead.estado = models.LeadEstado.interesado
        elif "descartar" in msg_lower:
            lead.estado = models.LeadEstado.descartado
    elif comando == "crear" and lead.estado == models.LeadEstado.nuevo:
        pass  # ya está en nuevo
    elif comando == "actualizar":
        if lead.estado == models.LeadEstado.nuevo:
            lead.estado = models.LeadEstado.interesado

    db.commit()
    db.refresh(lead)
    return lead


# ── Sentence splitter ─────────────────────────────────────────────────────────
def split_sentences(texto: str) -> list[str]:
    """Divide el texto en oraciones para envío progresivo."""
    sentences = re.split(r'(?<=[.!?])\s+', texto.strip())
    result = []
    for s in sentences:
        s = s.strip()
        if s:
            result.append(s)
    return result if result else [texto]


# ── Main agent function ───────────────────────────────────────────────────────
async def procesar_mensaje(
    canal_id: str,
    texto: str,
    canal: str,
    db: Session,
    username: str = "",
    caption_post: str = "",
    usar_debounce: bool = True,
) -> list[str]:
    """
    Procesa un mensaje del usuario y devuelve lista de oraciones a enviar.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return ["El agente IA no está configurado. Por favor contacte al administrador."]

    # Debounce
    if usar_debounce:
        texto = await debounce_message(canal_id, texto, delay=20.0)

    # Recuperar historial de la conversación
    lead = db.query(models.Lead).filter_by(canal_id=canal_id).first()
    historial = []
    if lead:
        msgs = db.query(models.MensajeConversacion).filter_by(lead_id=lead.id).order_by(
            models.MensajeConversacion.created_at
        ).all()
        for m in msgs[-20:]:  # últimos 20 mensajes (10 turnos)
            historial.append({"role": m.rol, "content": m.contenido})

    # Construir prompt de usuario con contexto
    user_content = f"MENSAJE DEL USUARIO:\n{texto}"
    if caption_post:
        user_content += f"\n\nCONTEXTO DEL POST (si respondió a uno):\n{caption_post}"
    user_content += f"\n\nfecha actual: {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    historial.append({"role": "user", "content": user_content})

    # Llamada a Claude con tool_use
    client = anthropic.Anthropic(api_key=api_key)

    messages = historial.copy()
    output_json = None

    for _ in range(5):  # máximo 5 iteraciones (tool calls)
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            # Ejecutar tools
            tool_results = []
            assistant_msg = {"role": "assistant", "content": response.content}
            messages.append(assistant_msg)

            for block in response.content:
                if block.type == "tool_use":
                    result = _ejecutar_tool(block.name, block.input, db)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            # Extraer texto de la respuesta
            raw = ""
            for block in response.content:
                if hasattr(block, "text"):
                    raw += block.text

            # Parsear JSON de salida
            clean = re.sub(r"```json|```", "", raw).strip()
            try:
                output_json = json.loads(clean)
            except Exception:
                output_json = {"respuesta": raw, "comando": "nada", "mensaje_comando": ""}
            break

    if not output_json:
        return ["Disculpá, tuve un problema procesando tu mensaje. Intentá de nuevo."]

    respuesta_texto = output_json.get("respuesta", "")
    comando = output_json.get("comando", "nada")
    mensaje_cmd = output_json.get("mensaje_comando", "")

    # Guardar mensaje del usuario y respuesta en historial
    if not lead:
        lead = _aplicar_crm(comando, mensaje_cmd, canal_id, canal, db)
        if username:
            lead.canal_username = username
            db.commit()
    else:
        _aplicar_crm(comando, mensaje_cmd, canal_id, canal, db)

    lead = db.query(models.Lead).filter_by(canal_id=canal_id).first()

    db.add(models.MensajeConversacion(lead_id=lead.id, rol="user", contenido=texto))
    db.add(models.MensajeConversacion(lead_id=lead.id, rol="assistant", contenido=respuesta_texto))
    db.commit()

    return split_sentences(respuesta_texto)
