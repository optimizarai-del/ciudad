"""
Módulo VENTAS — modelo de datos AISLADO.

Todas las tablas llevan prefijo `ventas_` y NO tienen foreign keys hacia
tablas de otros módulos (alquileres, contratos, etc.). La única referencia
externa permitida es `users.id` para identificar al vendedor/admin que opera
el módulo (auth compartida), nunca datos de negocio.

Single-tenant: todas las tablas reservan `workspace_id` (default 1) para
poder hacer el split a multi-tenant más adelante sin migración destructiva.

Ver plan: Plan_Maestro_Implementacion_CIUDAD_Ventas.md (sección 14 y 15).
"""
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Column, Integer, String, DateTime, Date, Float, Boolean, ForeignKey,
    Enum as SQLEnum, Text,
)
from sqlalchemy.orm import relationship

from app.database import Base

WORKSPACE_DEFAULT = 1


# ───────────────────────── Enums ─────────────────────────

class VPropiedadTipo(str, Enum):
    casa = "casa"
    departamento = "departamento"
    lote = "lote"
    local = "local"
    oficina = "oficina"
    galpon = "galpon"
    campo = "campo"
    otro = "otro"


class VPropiedadEstado(str, Enum):
    disponible = "disponible"
    reservada = "reservada"
    vendida = "vendida"
    inactiva = "inactiva"


class VPropiedadFuente(str, Enum):
    propia = "propia"          # cargada a mano por el equipo
    tokko = "tokko"            # Fase 2
    scraping = "scraping"      # Fase 4
    instagram = "instagram"    # Fase 4


class PedidoEstado(str, Enum):
    """Etapas del funnel comercial (kanban).

    NOTA — Agente interno IA (futuro): cuando se construya el agente, al pedirle
    información de un inmueble debe preguntar si la búsqueda es para un cliente
    puntual. Si lo es, asocia la búsqueda a ese cliente (crea/actualiza su
    pedido) y mueve al cliente al estado `esperando_respuesta`. El agente debe
    ser PROACTIVO actualizando el sistema interno (notas, estado del pedido,
    propiedades vinculadas) sin que el vendedor lo haga a mano. Ver plan
    sección 14, nota de Agente IA.
    """
    nuevo = "nuevo"
    contactado = "contactado"
    en_seguimiento = "en_seguimiento"
    esperando_respuesta = "esperando_respuesta"
    negociando = "negociando"
    cerrado = "cerrado"
    perdido = "perdido"


class PedidoPrioridad(str, Enum):
    baja = "baja"
    media = "media"
    alta = "alta"


class OperacionEstado(str, Enum):
    abierta = "abierta"
    sena = "sena"
    cerrada = "cerrada"
    caida = "caida"


class OfertaTipo(str, Enum):
    oferta = "oferta"
    contraoferta = "contraoferta"


class OfertaParte(str, Enum):
    comprador = "comprador"
    vendedor = "vendedor"


class OfertaEstado(str, Enum):
    pendiente = "pendiente"
    aceptada = "aceptada"
    rechazada = "rechazada"
    vencida = "vencida"


class ContactoTipo(str, Enum):
    colega = "colega"
    inmobiliaria = "inmobiliaria"
    escribano = "escribano"
    proveedor = "proveedor"
    otro = "otro"


class AuditAccion(str, Enum):
    create = "create"
    update = "update"
    delete = "delete"


# ───────────────────── Vendedor (perfil) ─────────────────────

class VentasVendedor(Base):
    """Perfil de ventas de un usuario. El auth sigue en `users`; acá vive la
    config específica del módulo (comisión por defecto, notificaciones)."""
    __tablename__ = "ventas_vendedores"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    nombre = Column(String, nullable=False)
    es_admin = Column(Boolean, default=False)   # rol ventas_admin
    activo = Column(Boolean, default=True)

    # Comisión por defecto del vendedor (%). Configurable y sobreescribible
    # por producto en ventas_comision_config (Mod #4).
    comision_default_pct = Column(Float, default=3.0)

    # Notificación diaria agrupada de matches (Mod #9)
    notif_matches_activa = Column(Boolean, default=True)
    hora_notif_matches = Column(String, default="09:00")  # "HH:MM"

    created_at = Column(DateTime, default=datetime.utcnow)


# ───────────────────── Cliente CRM ─────────────────────

class VentasCliente(Base):
    __tablename__ = "ventas_clientes"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    vendedor_id = Column(Integer, ForeignKey("ventas_vendedores.id"), index=True)

    nombre = Column(String, nullable=False)
    telefono = Column(String)
    email = Column(String)
    origen = Column(String)          # cómo llegó: referido, web, instagram, etc.
    observaciones = Column(Text)

    # true cuando ya cerró al menos una operación → grupo "clientes operados"
    es_operado = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    notas = relationship("VentasClienteNota", back_populates="cliente",
                         cascade="all, delete-orphan")


class VentasClienteNota(Base):
    """Hilo de notas por cliente (Mod #6). Cargables por web y por Telegram."""
    __tablename__ = "ventas_cliente_notas"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    cliente_id = Column(Integer, ForeignKey("ventas_clientes.id"), index=True, nullable=False)
    vendedor_id = Column(Integer, ForeignKey("ventas_vendedores.id"))
    texto = Column(Text, nullable=False)
    origen = Column(String, default="web")   # web | telegram
    created_at = Column(DateTime, default=datetime.utcnow)

    cliente = relationship("VentasCliente", back_populates="notas")


# ───────────────────── Propiedad ─────────────────────

class VentasPropiedad(Base):
    __tablename__ = "ventas_propiedades"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    cargada_por = Column(Integer, ForeignKey("ventas_vendedores.id"))

    titulo = Column(String)
    tipo = Column(SQLEnum(VPropiedadTipo), default=VPropiedadTipo.casa)
    estado = Column(SQLEnum(VPropiedadEstado), default=VPropiedadEstado.disponible)
    fuente = Column(SQLEnum(VPropiedadFuente), default=VPropiedadFuente.propia)

    # Ubicación
    direccion = Column(String)
    ciudad = Column(String)
    barrio_id = Column(Integer, ForeignKey("ventas_barrios.id"), index=True)  # Mod #5
    lat = Column(Float)
    lng = Column(Float)

    # Características
    precio_usd = Column(Float)
    superficie_m2 = Column(Float)
    dormitorios = Column(Integer)
    banos = Column(Integer)
    antiguedad_anios = Column(Integer)

    descripcion = Column(Text)
    apreciacion = Column(Text)        # apreciación personal del vendedor
    link_externo = Column(String)     # link a la publicación / inmobiliaria
    inmobiliaria = Column(String)     # quién la tiene (si es de un colega)

    # link opcional al contacto que la pasó (Mod #3)
    contacto_id = Column(Integer, ForeignKey("ventas_contactos.id"))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    barrio = relationship("VentasBarrio")
    ofertas = relationship("VentasOferta", back_populates="propiedad",
                           cascade="all, delete-orphan")


# ───────────────────── Pedido (búsqueda activa) ─────────────────────

class VentasPedido(Base):
    __tablename__ = "ventas_pedidos"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    cliente_id = Column(Integer, ForeignKey("ventas_clientes.id"), index=True, nullable=False)
    vendedor_id = Column(Integer, ForeignKey("ventas_vendedores.id"), index=True)

    estado = Column(SQLEnum(PedidoEstado), default=PedidoEstado.nuevo, index=True)
    prioridad = Column(SQLEnum(PedidoPrioridad), default=PedidoPrioridad.media)

    # Criterios de búsqueda
    tipo = Column(SQLEnum(VPropiedadTipo))
    zona = Column(String)              # texto libre / barrio buscado
    barrio_id = Column(Integer, ForeignKey("ventas_barrios.id"))
    precio_min_usd = Column(Float)
    precio_max_usd = Column(Float)
    dormitorios_min = Column(Integer)
    banos_min = Column(Integer)
    superficie_min_m2 = Column(Float)

    detalle = Column(Text)            # texto libre de lo que pidió el cliente
    orden_kanban = Column(Integer, default=0)  # posición dentro de la columna

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VentasPedidoPropiedad(Base):
    """Propiedades vinculadas/mostradas a un pedido (interés manual o match)."""
    __tablename__ = "ventas_pedido_propiedad"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    pedido_id = Column(Integer, ForeignKey("ventas_pedidos.id"), index=True, nullable=False)
    propiedad_id = Column(Integer, ForeignKey("ventas_propiedades.id"), index=True, nullable=False)
    estado = Column(String, default="sugerida")  # sugerida | mostrada | descartada
    nota = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


# ───────────────────── Oferta / Contraoferta (Mod #2) ─────────────────────

class VentasOferta(Base):
    __tablename__ = "ventas_ofertas"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    propiedad_id = Column(Integer, ForeignKey("ventas_propiedades.id"), index=True, nullable=False)
    cliente_id = Column(Integer, ForeignKey("ventas_clientes.id"), index=True)
    pedido_id = Column(Integer, ForeignKey("ventas_pedidos.id"))
    vendedor_id = Column(Integer, ForeignKey("ventas_vendedores.id"))

    monto_usd = Column(Float, nullable=False)
    tipo = Column(SQLEnum(OfertaTipo), default=OfertaTipo.oferta)
    parte = Column(SQLEnum(OfertaParte), default=OfertaParte.comprador)
    estado = Column(SQLEnum(OfertaEstado), default=OfertaEstado.pendiente, index=True)
    responde_a_id = Column(Integer, ForeignKey("ventas_ofertas.id"))  # hilo
    nota = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    propiedad = relationship("VentasPropiedad", back_populates="ofertas")


# ───────────────────── Operación cerrada ─────────────────────

class VentasOperacion(Base):
    __tablename__ = "ventas_operaciones"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    propiedad_id = Column(Integer, ForeignKey("ventas_propiedades.id"), index=True)
    cliente_id = Column(Integer, ForeignKey("ventas_clientes.id"), index=True)
    pedido_id = Column(Integer, ForeignKey("ventas_pedidos.id"))
    vendedor_id = Column(Integer, ForeignKey("ventas_vendedores.id"), index=True)

    estado = Column(SQLEnum(OperacionEstado), default=OperacionEstado.abierta)
    monto_cierre_usd = Column(Float)
    fecha_cierre = Column(Date)

    # Comisión (Mod #4): se calcula automático pero puede sobreescribirse a mano
    comision_pct = Column(Float)
    comision_monto_usd = Column(Float)
    comision_manual = Column(Boolean, default=False)

    notas = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VentasComisionConfig(Base):
    """Configuración de comisión por vendedor y por tipo de producto (Mod #4).
    Si no hay fila para (vendedor, tipo), se usa comision_default_pct del
    vendedor. La carga manual en la operación gana sobre todo esto."""
    __tablename__ = "ventas_comision_config"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    vendedor_id = Column(Integer, ForeignKey("ventas_vendedores.id"), index=True, nullable=False)
    tipo = Column(SQLEnum(VPropiedadTipo))   # null = aplica a todos los tipos
    comision_pct = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ───────────────────── Red de contactos (Mod #3) ─────────────────────

class VentasContacto(Base):
    __tablename__ = "ventas_contactos"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    vendedor_id = Column(Integer, ForeignKey("ventas_vendedores.id"), index=True, nullable=False)

    nombre = Column(String, nullable=False)
    tipo = Column(SQLEnum(ContactoTipo), default=ContactoTipo.colega)
    telefono = Column(String)
    email = Column(String)
    empresa = Column(String)
    notas = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)


# ───────────────────── Barrios + valor m² (Mod #5 / #1) ─────────────────────

class VentasBarrio(Base):
    __tablename__ = "ventas_barrios"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    nombre = Column(String, nullable=False)
    ciudad = Column(String)
    poligono_geojson = Column(Text)   # GeoJSON con los límites del barrio
    color = Column(String, default="#B8893A")
    created_at = Column(DateTime, default=datetime.utcnow)


class VentasValorM2Referencia(Base):
    """Valor/m² de referencia por barrio+tipo. Fallback de la tasación cuando
    no hay comparables suficientes (Mod #1)."""
    __tablename__ = "ventas_valor_m2_referencia"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    barrio_id = Column(Integer, ForeignKey("ventas_barrios.id"), index=True)
    tipo = Column(SQLEnum(VPropiedadTipo))
    valor_m2_usd = Column(Float, nullable=False)
    actualizado_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VentasTasacion(Base):
    """Tasación automática por comparables (Mod #1)."""
    __tablename__ = "ventas_tasaciones"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    generado_por = Column(Integer, ForeignKey("ventas_vendedores.id"))

    # Sujeto de la tasación
    tipo = Column(SQLEnum(VPropiedadTipo))
    barrio_id = Column(Integer, ForeignKey("ventas_barrios.id"))
    direccion = Column(String)
    superficie_m2 = Column(Float)
    dormitorios = Column(Integer)
    banos = Column(Integer)
    antiguedad_anios = Column(Integer)
    estado_conservacion = Column(String)   # nuevo | bueno | a_refaccionar

    # Resultado
    valor_m2_usado = Column(Float)
    valor_min_usd = Column(Float)
    valor_medio_usd = Column(Float)
    valor_max_usd = Column(Float)
    confianza = Column(String)             # alta | media | baja
    metodo = Column(String)                # comparables | referencia
    comparables_json = Column(Text)        # IDs y datos de los comps usados
    informe_texto = Column(Text)           # narrativa IA (Fase 3)

    created_at = Column(DateTime, default=datetime.utcnow)


# ───────────────────── Audit log ─────────────────────

class VentasAuditLog(Base):
    __tablename__ = "ventas_audit_log"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    vendedor_id = Column(Integer, ForeignKey("ventas_vendedores.id"))
    entidad = Column(String)        # tabla afectada
    entidad_id = Column(Integer)
    accion = Column(SQLEnum(AuditAccion))
    detalle = Column(Text)          # JSON con el diff / payload
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ═══════════════════════════════════════════════════════════════════════
#  FASE 2 — Tokko + Telegram + Notificaciones
# ═══════════════════════════════════════════════════════════════════════

class VentasTokkoConfig(Base):
    """Config de la integración Tokko (Fase 2). Single-tenant: una fila.
    `ciudades_json` segmenta el scraping a ciertas ciudades (Mod #7)."""
    __tablename__ = "ventas_tokko_config"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    api_key = Column(String)              # API key Tokko (cifrar en prod)
    activo = Column(Boolean, default=False)
    ciudades_json = Column(Text)          # JSON: ["Santa Rosa", "General Pico"]
    sync_cada_horas = Column(Integer, default=4)
    ultima_sync = Column(DateTime)
    ultima_sync_resultado = Column(Text)  # resumen de la última corrida
    created_at = Column(DateTime, default=datetime.utcnow)


class VentasTelegramLink(Base):
    """Vinculación vendedor ↔ chat de Telegram (Fase 2). La vinculación se
    hace con un token one-time generado desde la web (TTL 10 min)."""
    __tablename__ = "ventas_telegram_links"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    vendedor_id = Column(Integer, ForeignKey("ventas_vendedores.id"), unique=True, index=True)
    chat_id = Column(String, index=True)         # null hasta que confirma /start
    token = Column(String, index=True)           # token one-time
    token_expira = Column(DateTime)
    vinculado = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class NotifTipo(str, Enum):
    match = "match"
    tarea = "tarea"
    asignacion = "asignacion"
    sistema = "sistema"


class VentasNotificacion(Base):
    """Histórico de notificaciones al vendedor (Fase 2/3). Persistido incluso
    si todavía no tiene Telegram vinculado."""
    __tablename__ = "ventas_notificaciones"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    vendedor_id = Column(Integer, ForeignKey("ventas_vendedores.id"), index=True)
    tipo = Column(SQLEnum(NotifTipo), default=NotifTipo.sistema)
    titulo = Column(String)
    cuerpo = Column(Text)
    payload_json = Column(Text)           # data extra (ids, links)
    leida = Column(Boolean, default=False)
    enviada_telegram = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ═══════════════════════════════════════════════════════════════════════
#  FASE 3 — Post-venta (tareas) + Motor de match
# ═══════════════════════════════════════════════════════════════════════

class TareaTipo(str, Enum):
    seguimiento_postventa = "seguimiento_postventa"
    llamado = "llamado"
    visita = "visita"
    otro = "otro"


class TareaEstado(str, Enum):
    pendiente = "pendiente"
    hecha = "hecha"
    vencida = "vencida"


class VentasPlantillaSeguimiento(Base):
    """Plantilla de seguimiento post-venta configurable (Fase 3). Cada fila es
    un recordatorio a `offset_dias` desde el cierre de la operación."""
    __tablename__ = "ventas_plantillas_seguimiento"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    nombre = Column(String, nullable=False)
    offset_dias = Column(Integer, nullable=False)   # 30, 180, 365…
    activa = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class VentasTarea(Base):
    """Tarea / recordatorio (Fase 3). Generada por plantillas post-venta o a
    mano. El cron diario marca las vencidas y notifica."""
    __tablename__ = "ventas_tareas"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    vendedor_id = Column(Integer, ForeignKey("ventas_vendedores.id"), index=True)
    cliente_id = Column(Integer, ForeignKey("ventas_clientes.id"))
    operacion_id = Column(Integer, ForeignKey("ventas_operaciones.id"))

    tipo = Column(SQLEnum(TareaTipo), default=TareaTipo.seguimiento_postventa)
    descripcion = Column(String, nullable=False)
    vencimiento = Column(Date, index=True)
    estado = Column(SQLEnum(TareaEstado), default=TareaEstado.pendiente, index=True)
    notificada = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class MatchEstado(str, Enum):
    pendiente = "pendiente"
    mostrado = "mostrado"
    descartado = "descartado"


class VentasMatch(Base):
    """Match pedido ↔ propiedad (Fase 3). Único por (pedido, propiedad)."""
    __tablename__ = "ventas_matches"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, default=WORKSPACE_DEFAULT, index=True)
    pedido_id = Column(Integer, ForeignKey("ventas_pedidos.id"), index=True, nullable=False)
    propiedad_id = Column(Integer, ForeignKey("ventas_propiedades.id"), index=True, nullable=False)
    vendedor_id = Column(Integer, ForeignKey("ventas_vendedores.id"), index=True)

    score = Column(Integer, default=0)
    razones_json = Column(Text)           # JSON: [{"motivo":..,"puntos":..}]
    estado = Column(SQLEnum(MatchEstado), default=MatchEstado.pendiente, index=True)
    notificado = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
