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
    operador = "operador"
    finanzas = "finanzas"
    agente_ia = "agente_ia"


class PropiedadTipo(str, Enum):
    departamento = "departamento"
    casa = "casa"
    local = "local"
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


class ContratoTipo(str, Enum):
    alquiler_vivienda = "alquiler_vivienda"
    alquiler_comercial = "alquiler_comercial"
    boleto_compraventa = "boleto_compraventa"


class ContratoEstado(str, Enum):
    borrador = "borrador"
    vigente = "vigente"
    vencido = "vencido"
    rescindido = "rescindido"
    cerrado = "cerrado"


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
    role = Column(SQLEnum(UserRole), default=UserRole.operador)
    is_active = Column(Boolean, default=True)
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

    propietario_id = Column(Integer, ForeignKey("clientes.id"))
    propietario = relationship("Cliente", foreign_keys=[propietario_id])
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
    notas = Column(Text)
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
    created_at = Column(DateTime, default=datetime.utcnow)

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
