from datetime import datetime, date
from enum import Enum
from sqlalchemy import (
    Column, Integer, String, DateTime, Date, Float, Boolean, ForeignKey,
    Enum as SQLEnum, Text
)
from sqlalchemy.orm import relationship
from app.database import Base


class UserRole(str, Enum):
    admin = "admin"
    gerencia = "gerencia"
    alquileres = "alquileres"
    ventas = "ventas"
    agente_ia = "agente_ia"
    # Workspace aislado: este usuario solo ve y crea registros con
    # is_demo=True. El resto de los roles ven únicamente los registros
    # con is_demo=False (datos "reales" del estudio).
    admin_demo = "admin_demo"


class PropiedadTipo(str, Enum):
    departamento = "departamento"
    casa = "casa"
    local = "local"
    oficina = "oficina"
    galpon = "galpon"
    campo = "campo"


class PropiedadModalidad(str, Enum):
    alquiler = "alquiler"
    venta = "venta"
    ambas = "ambas"


class PropiedadEstado(str, Enum):
    disponible = "disponible"
    ocupada = "ocupada"
    reservada = "reservada"
    inactiva = "inactiva"


class ClienteRol(str, Enum):
    propietario = "propietario"
    inquilino = "inquilino"
    comprador = "comprador"
    vendedor = "vendedor"


class ClienteEtapaVenta(str, Enum):
    """Etapa del pipeline comercial de un cliente del área de Ventas.

    Sólo aplica a clientes con rol=comprador/vendedor. Se usa para
    seguimiento en CRM: el operador puede mover un prospecto a "seña"
    cuando deja la reserva, a "comprador" cuando cierra, etc.
    """
    prospecto = "prospecto"           # primer contacto, evaluando
    seguimiento = "seguimiento"       # se le hace follow-up periódico
    sena = "sena"                     # dejó una seña / reserva
    comprador = "comprador"           # cerró la compra
    no_interesado = "no_interesado"   # descartado, no avanza


class ContratoTipo(str, Enum):
    alquiler_vivienda = "alquiler_vivienda"
    alquiler_comercial = "alquiler_comercial"
    boleto_compraventa = "boleto_compraventa"
    sena_alquiler = "sena_alquiler"


class ContratoEstado(str, Enum):
    borrador = "borrador"
    vigente = "vigente"
    vencido = "vencido"
    rescindido = "rescindido"
    reservado = "reservado"


class IndiceAjuste(str, Enum):
    ipc = "ipc"
    icl = "icl"
    fijo = "fijo"
    sin_ajuste = "sin_ajuste"


class PagoEstado(str, Enum):
    pendiente = "pendiente"
    pagado = "pagado"
    vencido = "vencido"
    parcial = "parcial"


class EventoTipo(str, Enum):
    alta = "alta"
    pago = "pago"
    ajuste = "ajuste"
    vencimiento = "vencimiento"
    consulta_ia = "consulta_ia"
    nota = "nota"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    nombre = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    telefono = Column(String)
    password_hash = Column(String, nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.alquileres)
    is_active = Column(Boolean, default=True)
    # Vinculación a Telegram para el agente administrativo: si un mensaje llega
    # desde este chat_id, se ejecutan acciones con los permisos del usuario.
    telegram_chat_id = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Propiedad(Base):
    __tablename__ = "propiedades"
    id = Column(Integer, primary_key=True)
    codigo = Column(String, unique=True, index=True)
    direccion = Column(String, nullable=False, index=True)
    ciudad = Column(String)
    provincia = Column(String)
    tipo = Column(SQLEnum(PropiedadTipo), nullable=False)
    modalidad = Column(SQLEnum(PropiedadModalidad), default=PropiedadModalidad.alquiler)
    estado = Column(SQLEnum(PropiedadEstado), default=PropiedadEstado.disponible)
    superficie_m2 = Column(Float)
    ambientes = Column(Integer)
    descripcion = Column(Text)

    # Costos base
    precio_alquiler = Column(Float, default=0)
    precio_venta = Column(Float, default=0)
    expensas = Column(Float, default=0)
    impuesto_inmobiliario = Column(Float, default=0)
    tasa_municipal = Column(Float, default=0)

    # Integración Tokko
    tokko_id = Column(String, index=True)
    tokko_sync_at = Column(DateTime)

    # Padrón municipal (Santa Rosa La Pampa). Se usa para consultar la
    # tasa/deuda real desde https://consultadeuda.santarosa.gob.ar/
    numero_referencia = Column(String, index=True, nullable=True)
    tasa_consultada_at = Column(DateTime, nullable=True)
    # JSON con últimos cuotas/montos devueltos por la municipalidad
    tasa_detalle = Column(Text, nullable=True)

    propietario_id = Column(Integer, ForeignKey("clientes.id"))
    propietario = relationship("Cliente", foreign_keys=[propietario_id])
    # Aislamiento de workspace: True = pertenece al sandbox demo, False = data real.
    is_demo = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Cliente(Base):
    __tablename__ = "clientes"
    id = Column(Integer, primary_key=True)
    nombre = Column(String, nullable=False)
    apellido = Column(String)
    razon_social = Column(String)
    documento = Column(String, index=True)
    email = Column(String, index=True)
    telefono = Column(String)
    rol = Column(SQLEnum(ClienteRol), default=ClienteRol.inquilino)
    # Etapa del pipeline comercial. Sólo aplica cuando rol=comprador/vendedor
    # (los inquilinos/propietarios no tienen pipeline). Nullable.
    etapa_venta = Column(SQLEnum(ClienteEtapaVenta), nullable=True, index=True)
    notas = Column(Text)
    is_demo = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Contrato(Base):
    __tablename__ = "contratos"
    id = Column(Integer, primary_key=True)
    codigo = Column(String, unique=True, index=True)
    tipo = Column(SQLEnum(ContratoTipo), nullable=False)
    estado = Column(SQLEnum(ContratoEstado), default=ContratoEstado.borrador)

    propiedad_id = Column(Integer, ForeignKey("propiedades.id"), nullable=False)
    propiedad = relationship("Propiedad")
    inquilino_id = Column(Integer, ForeignKey("clientes.id"))
    inquilino = relationship("Cliente", foreign_keys=[inquilino_id])

    fecha_inicio = Column(Date)
    fecha_fin = Column(Date)
    monto_inicial = Column(Float, default=0)
    deposito = Column(Float, default=0)

    # Ajuste
    indice_ajuste = Column(SQLEnum(IndiceAjuste), default=IndiceAjuste.ipc)
    periodicidad_meses = Column(Integer, default=3)
    porcentaje_fijo = Column(Float, default=0)  # solo si indice = fijo

    # Comisión
    comision_porc = Column(Float, default=0)

    notas = Column(Text)
    is_demo = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Archivo del contrato firmado / actualizado manualmente (subido por el
    # admin tras editarlo en Word). Storage path en bucket ciudad-contratos.
    archivo_path = Column(String, nullable=True, index=True)
    archivo_nombre = Column(String, nullable=True)
    archivo_mime = Column(String, nullable=True)
    archivo_subido_at = Column(DateTime, nullable=True)

    pagos = relationship("Pago", back_populates="contrato", cascade="all, delete")
    ajustes = relationship("AjusteContrato", back_populates="contrato", cascade="all, delete")


class AjusteContrato(Base):
    __tablename__ = "ajustes_contrato"
    id = Column(Integer, primary_key=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"))
    contrato = relationship("Contrato", back_populates="ajustes")
    fecha = Column(Date, default=date.today)
    porcentaje = Column(Float, default=0)
    monto_anterior = Column(Float)
    monto_nuevo = Column(Float)
    indice_usado = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class Pago(Base):
    __tablename__ = "pagos"
    id = Column(Integer, primary_key=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"))
    contrato = relationship("Contrato", back_populates="pagos")
    periodo = Column(String)  # ej "2026-04"
    fecha_vencimiento = Column(Date)
    fecha_pago = Column(Date)
    monto_alquiler = Column(Float, default=0)
    monto_expensas = Column(Float, default=0)
    monto_impuestos = Column(Float, default=0)
    monto_municipal = Column(Float, default=0)
    monto_otros = Column(Float, default=0)
    monto_total = Column(Float, default=0)
    estado = Column(SQLEnum(PagoEstado), default=PagoEstado.pendiente)
    notas = Column(Text)
    # Liquidación al propietario: cuando el inquilino paga, el propietario
    # todavía no cobró su parte. Cuando viene a buscar el dinero, la
    # inmobiliaria marca el pago como "liquidado" y se registra cuándo y
    # cuánto neto se le entregó. Antes de ese momento, el pago figura como
    # "pendiente de liquidar" en la página de Liquidaciones.
    liquidado_propietario = Column(Boolean, default=False, nullable=False, index=True)
    fecha_liquidacion_propietario = Column(Date, nullable=True)
    monto_liquidado_propietario = Column(Float, nullable=True)
    notas_liquidacion = Column(Text)
    is_demo = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Evento(Base):
    __tablename__ = "eventos"
    id = Column(Integer, primary_key=True)
    tipo = Column(SQLEnum(EventoTipo), default=EventoTipo.nota)
    titulo = Column(String, nullable=False)
    descripcion = Column(Text)
    propiedad_id = Column(Integer, ForeignKey("propiedades.id"))
    contrato_id = Column(Integer, ForeignKey("contratos.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    es_critico = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ConsultaIA(Base):
    __tablename__ = "consultas_ia"
    id = Column(Integer, primary_key=True)
    telefono = Column(String, index=True)
    input_text = Column(Text)
    intent = Column(String)
    respuesta = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)


class LeadEstado(str, Enum):
    nuevo = "nuevo"
    interesado = "interesado"
    a_contactar = "a_contactar"
    descartado = "descartado"

class LeadCanal(str, Enum):
    telegram = "telegram"
    instagram = "instagram"
    whatsapp = "whatsapp"
    web = "web"

class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True)
    canal = Column(SQLEnum(LeadCanal), default=LeadCanal.telegram)
    canal_id = Column(String, index=True)          # chat_id telegram / ig user_id
    canal_username = Column(String)
    nombre = Column(String)
    telefono = Column(String)
    email = Column(String)
    estado = Column(SQLEnum(LeadEstado), default=LeadEstado.nuevo)
    operacion = Column(String)                      # alquiler/venta/vender
    tipo_propiedad = Column(String)
    zona = Column(String)
    habitaciones = Column(String)
    presupuesto = Column(String)
    notas_crm = Column(Text)
    is_demo = Column(Boolean, default=False, nullable=False, index=True)
    ultima_actividad = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    mensajes = relationship("MensajeConversacion", back_populates="lead", cascade="all, delete")

class MensajeConversacion(Base):
    __tablename__ = "mensajes_conversacion"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id"))
    lead = relationship("Lead", back_populates="mensajes")
    rol = Column(String)   # "user" | "assistant"
    contenido = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class AdjuntoTipo(str, Enum):
    foto = "foto"
    documento = "documento"
    plano = "plano"
    otro = "otro"


class PropiedadAdjunto(Base):
    __tablename__ = "propiedad_adjuntos"
    id = Column(Integer, primary_key=True)
    propiedad_id = Column(Integer, ForeignKey("propiedades.id"), nullable=False, index=True)
    propiedad = relationship("Propiedad")
    tipo = Column(SQLEnum(AdjuntoTipo), default=AdjuntoTipo.foto)
    nombre_archivo = Column(String, nullable=False)
    mime = Column(String)
    tamano_bytes = Column(Integer)
    descripcion = Column(Text)
    # Legacy: blob inline en la DB. Se mantiene nullable para que las filas
    # nuevas vayan directo a Supabase Storage (ver `storage_path`).
    blob_b64 = Column(Text, nullable=True)
    storage_path = Column(String, nullable=True, index=True)
    es_principal = Column(Boolean, default=False)  # foto destacada
    created_at = Column(DateTime, default=datetime.utcnow)


class RefaccionPagador(str, Enum):
    """Quién pone la plata de la refacción.

    - inquilino: el inquilino paga (típicamente lo factura él y queremos
      descontarlo del próximo alquiler).
    - propietario: el propietario paga; se descuenta de la liquidación que
      le mandamos al propietario, no del cobro al inquilino.
    """
    inquilino = "inquilino"
    propietario = "propietario"


class RefaccionEstado(str, Enum):
    pendiente = "pendiente"      # cargada, todavía no descontada
    aplicada = "aplicada"        # ya se descontó de un pago
    cancelada = "cancelada"      # se anuló (no aplica)


class Refaccion(Base):
    """Refacción/arreglo hecho en una propiedad.

    Si la paga el inquilino, queda con estado=pendiente y al registrar el
    próximo pago del alquiler se descuenta automáticamente (monto pasa al
    campo `monto_otros` del pago con signo negativo o se resta del total).
    Si la paga el propietario, se incluye como gasto en la liquidación
    mensual que se le manda.
    """
    __tablename__ = "refacciones"
    id = Column(Integer, primary_key=True)
    propiedad_id = Column(Integer, ForeignKey("propiedades.id"), nullable=False, index=True)
    propiedad = relationship("Propiedad")
    contrato_id = Column(Integer, ForeignKey("contratos.id"), nullable=True, index=True)
    contrato = relationship("Contrato")

    fecha = Column(Date, default=date.today, nullable=False)
    descripcion = Column(String, nullable=False)
    monto = Column(Float, default=0, nullable=False)
    pagador = Column(SQLEnum(RefaccionPagador), default=RefaccionPagador.inquilino, nullable=False)
    estado = Column(SQLEnum(RefaccionEstado), default=RefaccionEstado.pendiente, nullable=False)
    # Si fue descontada en un pago concreto, queda apuntando a ese pago
    pago_id = Column(Integer, ForeignKey("pagos.id"), nullable=True, index=True)
    pago = relationship("Pago")

    notas = Column(Text)
    is_demo = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ComprobanteTipo(str, Enum):
    inquilino = "inquilino"
    propietario = "propietario"


class Comprobante(Base):
    __tablename__ = "comprobantes"
    id = Column(Integer, primary_key=True)
    pago_id = Column(Integer, ForeignKey("pagos.id"), nullable=False, index=True)
    pago = relationship("Pago")
    tipo = Column(SQLEnum(ComprobanteTipo), nullable=False)
    destinatario_nombre = Column(String)
    destinatario_email = Column(String)
    monto_total = Column(Float, default=0)
    monto_comision = Column(Float, default=0)   # solo en propietario
    monto_neto = Column(Float, default=0)       # solo en propietario
    # Legacy: PDF inline. Las filas nuevas suben a Storage (ver storage_path).
    pdf_blob = Column(Text, nullable=True)
    storage_path = Column(String, nullable=True, index=True)
    enviado_email = Column(Boolean, default=False)
    fecha_envio = Column(DateTime)
    error_envio = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
