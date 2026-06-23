"""
Asistente IA dentro de la plataforma (web app).

Agente conversacional real (Claude + tool-calling) que responde preguntas del
staff sobre los datos del sistema. A diferencia del agente de Telegram, este
corre autenticado en la web y **lo que puede informar depende del rol** del
usuario logueado:

- ventas / ventas_admin  → datos del CRM de Ventas (pedidos, propiedades en
  venta, clientes, operaciones, matches).
- alquileres / finanzas  → datos de Alquileres (propiedades, contratos,
  cobranza, dashboard) — reusa las tools read-only de `agente_admin`.
- admin / admin_demo / gerencia → ambos mundos.

Es de SOLO LECTURA: informa, no modifica (las modificaciones siguen estando en
sus pantallas y en el agente admin de Telegram).

Si no hay ANTHROPIC_API_KEY, devuelve un mensaje claro en vez de fallar.
"""
import os
import json

from sqlalchemy.orm import Session

from app import models_ventas as mv
from app.services import agente_admin as adm

# ── Tools de Alquileres reutilizadas (solo lectura) ──────────────────────────
_ALQ_READ = {"buscar_propiedad", "info_propiedad", "info_contrato",
             "listar_pendientes_cobro", "resumen_dashboard", "calcular_alquiler"}
ALQ_TOOLS = {k: v for k, v in adm.TOOLS.items() if k in _ALQ_READ}
ALQ_SCHEMAS = [s for s in adm.TOOL_SCHEMAS if s["name"] in _ALQ_READ]


def _val(x):
    return x.value if hasattr(x, "value") else x


# ── Tools de Ventas (CRM) — solo lectura ─────────────────────────────────────
def ventas_resumen(db: Session, **_):
    props = db.query(mv.VentasPropiedad).all()
    pedidos = db.query(mv.VentasPedido).all()
    activos = [p for p in pedidos if _val(p.estado) not in ("cerrado", "perdido")]
    ops = db.query(mv.VentasOperacion).all()
    matches = db.query(mv.VentasMatch).filter(mv.VentasMatch.estado == "pendiente").count()
    return {
        "clientes": db.query(mv.VentasCliente).count(),
        "propiedades_en_venta": len(props),
        "pedidos_totales": len(pedidos),
        "pedidos_activos": len(activos),
        "operaciones": len(ops),
        "matches_pendientes": matches,
    }


def ventas_buscar_propiedad(db: Session, query: str = "", tipo: str = "",
                            precio_max: float = None, limit: int = 10, **_):
    q = db.query(mv.VentasPropiedad)
    if tipo:
        q = q.filter(mv.VentasPropiedad.tipo == tipo)
    if precio_max:
        q = q.filter(mv.VentasPropiedad.precio_usd <= precio_max)
    rows = q.order_by(mv.VentasPropiedad.created_at.desc()).limit(200).all()
    if query:
        b = query.lower()
        rows = [p for p in rows if any(
            (getattr(p, f) or "").lower().find(b) >= 0
            for f in ("titulo", "direccion", "ciudad", "inmobiliaria", "descripcion"))]
    rows = rows[:limit]
    return {"total": len(rows), "propiedades": [{
        "id": p.id, "titulo": p.titulo, "tipo": _val(p.tipo), "estado": _val(p.estado),
        "ciudad": p.ciudad, "direccion": p.direccion, "precio_usd": p.precio_usd,
        "dormitorios": p.dormitorios, "banos": p.banos, "fuente": _val(p.fuente),
        "inmobiliaria": p.inmobiliaria,
    } for p in rows]}


def ventas_buscar_cliente(db: Session, query: str = "", limit: int = 10, **_):
    rows = db.query(mv.VentasCliente).all()
    if query:
        b = query.lower()
        rows = [c for c in rows if any(
            (getattr(c, f) or "").lower().find(b) >= 0
            for f in ("nombre", "telefono", "email", "origen"))]
    rows = rows[:limit]
    out = []
    for c in rows:
        peds = db.query(mv.VentasPedido).filter_by(cliente_id=c.id).all()
        out.append({
            "id": c.id, "nombre": c.nombre, "telefono": c.telefono, "email": c.email,
            "es_operado": c.es_operado, "origen": c.origen,
            "pedidos": [{"tipo": _val(p.tipo), "zona": p.zona, "estado": _val(p.estado),
                         "precio_max_usd": p.precio_max_usd} for p in peds],
        })
    return {"total": len(out), "clientes": out}


def ventas_listar_pedidos(db: Session, estado: str = "", limit: int = 20, **_):
    q = db.query(mv.VentasPedido)
    if estado:
        q = q.filter(mv.VentasPedido.estado == estado)
    rows = q.order_by(mv.VentasPedido.created_at.desc()).limit(limit).all()
    def cli(cid):
        c = db.query(mv.VentasCliente).filter_by(id=cid).first()
        return c.nombre if c else f"#{cid}"
    return {"total": len(rows), "pedidos": [{
        "id": p.id, "cliente": cli(p.cliente_id), "tipo": _val(p.tipo), "zona": p.zona,
        "estado": _val(p.estado), "prioridad": _val(p.prioridad),
        "precio_max_usd": p.precio_max_usd, "dormitorios_min": p.dormitorios_min,
    } for p in rows]}


def ventas_top_matches(db: Session, limit: int = 10, **_):
    rows = (db.query(mv.VentasMatch)
            .filter(mv.VentasMatch.estado == "pendiente")
            .order_by(mv.VentasMatch.score.desc()).limit(limit).all())
    out = []
    for m in rows:
        ped = db.query(mv.VentasPedido).filter_by(id=m.pedido_id).first()
        prop = db.query(mv.VentasPropiedad).filter_by(id=m.propiedad_id).first()
        cli = db.query(mv.VentasCliente).filter_by(id=ped.cliente_id).first() if ped else None
        out.append({
            "score": m.score,
            "cliente": cli.nombre if cli else None,
            "propiedad": (prop.titulo or prop.direccion) if prop else None,
            "precio_usd": prop.precio_usd if prop else None,
        })
    return {"total": len(out), "matches": out}


VENTAS_TOOLS = {
    "ventas_resumen": ventas_resumen,
    "ventas_buscar_propiedad": ventas_buscar_propiedad,
    "ventas_buscar_cliente": ventas_buscar_cliente,
    "ventas_listar_pedidos": ventas_listar_pedidos,
    "ventas_top_matches": ventas_top_matches,
}

VENTAS_SCHEMAS = [
    {"name": "ventas_resumen", "description": "Resumen del CRM de Ventas: clientes, pedidos activos, propiedades en venta, operaciones, matches pendientes.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "ventas_buscar_propiedad", "description": "Busca propiedades en venta por texto (dirección/ciudad/inmobiliaria), tipo y/o precio máximo.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"}, "tipo": {"type": "string"},
         "precio_max": {"type": "number"}, "limit": {"type": "integer", "default": 10}}}},
    {"name": "ventas_buscar_cliente", "description": "Busca clientes del CRM por nombre/teléfono/email y devuelve sus pedidos.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"}, "limit": {"type": "integer", "default": 10}}}},
    {"name": "ventas_listar_pedidos", "description": "Lista pedidos (búsquedas activas), opcionalmente filtrados por estado del funnel.",
     "input_schema": {"type": "object", "properties": {
         "estado": {"type": "string", "description": "nuevo|contactado|en_seguimiento|esperando_respuesta|negociando|cerrado|perdido"},
         "limit": {"type": "integer", "default": 20}}}},
    {"name": "ventas_top_matches", "description": "Mejores matches pendientes entre pedidos de clientes y propiedades, ordenados por score.",
     "input_schema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 10}}}},
]

# ── Registro unificado + gating por rol ──────────────────────────────────────
ALL_TOOLS = {**ALQ_TOOLS, **VENTAS_TOOLS}
ALL_SCHEMAS = ALQ_SCHEMAS + VENTAS_SCHEMAS

_VENTAS = set(VENTAS_TOOLS.keys())
_ALQ = set(ALQ_TOOLS.keys())

ROLE_TOOLS = {
    "admin":      _ALQ | _VENTAS,
    "admin_demo": _ALQ | _VENTAS,
    "gerencia":   _ALQ | _VENTAS,
    "alquileres": _ALQ,
    "finanzas":   _ALQ,
    "ventas":     _VENTAS,
    "ventas_admin": _VENTAS,
    "agente_ia":  _VENTAS | {"buscar_propiedad", "info_propiedad"},
}


def _ambito(role: str) -> str:
    tn = ROLE_TOOLS.get(role, set())
    tiene_v = bool(tn & _VENTAS)
    tiene_a = bool(tn & _ALQ)
    if tiene_v and tiene_a:
        return "Ventas (CRM) y Alquileres"
    if tiene_v:
        return "Ventas (CRM)"
    if tiene_a:
        return "Alquileres"
    return "ninguna área (rol sin permisos)"


SYSTEM = """Sos el asistente interno de IA de la plataforma CIUDAD — Negocios Inmobiliarios.
Hablás con un integrante del staff dentro de la web app. Respondé sus preguntas
consultando los datos reales del sistema con las herramientas disponibles.

Cómo trabajar:
- Entendé qué necesita y llamá a las tools que correspondan (podés encadenar varias).
- Respondé en español rioplatense, claro y conciso. Para listas usá viñetas.
- Mostrá números concretos (precios en USD, cantidades) cuando los tengas.
- No inventes datos: si una herramienta no devuelve resultados, decilo.
- Solo podés CONSULTAR información; no modificás nada. Si te piden cambiar algo,
  explicá que eso se hace desde la pantalla correspondiente.
- Importante: solo tenés acceso a la información del área habilitada para el rol
  del usuario. Si te preguntan por un área fuera de su alcance, aclaralo."""


def _fallback(role: str) -> str:
    return ("El asistente de IA todavía no está configurado (falta ANTHROPIC_API_KEY "
            "en el servidor). Cuando esté, vas a poder preguntarme sobre "
            f"{_ambito(role)} en lenguaje natural.")


def responder(texto: str, db: Session, role: str = "ventas", nombre: str = "") -> str:
    """Devuelve la respuesta del asistente para mostrar en el chat de la web."""
    permitidos = ROLE_TOOLS.get(role, set())
    if not permitidos:
        return f"Tu rol ({role}) no tiene acceso al asistente. Pedí permisos a un administrador."

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return _fallback(role)
    try:
        from anthropic import Anthropic
    except ImportError:
        return _fallback(role)

    schemas = [s for s in ALL_SCHEMAS if s["name"] in permitidos]
    system = SYSTEM + (
        f"\n\nUsuario: {nombre or 'Staff'} (rol: {role}). "
        f"Áreas habilitadas: {_ambito(role)}. "
        f"Tools disponibles: {', '.join(sorted(permitidos))}."
    )
    client = Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": texto}]

    try:
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
                if block.name not in permitidos:
                    out = {"ok": False, "error": f"acción no permitida para tu rol ({role})"}
                else:
                    fn = ALL_TOOLS.get(block.name)
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

      return "No pude resolver tu consulta después de varios intentos. Probá reformularla."
    except Exception as e:
        print(f"[agente_plataforma] error en la llamada a Claude: {e}")
        return ("Tuve un problema para procesar tu consulta. "
                "Si el problema persiste, avisá al administrador (puede ser un tema de configuración de la IA).")
