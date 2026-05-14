from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, EmailStr


# ---------- Auth ----------
class UserCreate(BaseModel):
    nombre: str
    email: EmailStr
    password: str
    telefono: Optional[str] = None
    role: Optional[str] = "alquileres"


class UserOut(BaseModel):
    id: int
    nombre: str
    email: str
    telefono: Optional[str] = None
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Cliente ----------
class ClienteBase(BaseModel):
    nombre: str
    apellido: Optional[str] = None
    razon_social: Optional[str] = None
    documento: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    rol: Optional[str] = "inquilino"
    # Solo para clientes del área de ventas. Valores válidos:
    # prospecto, seguimiento, sena, comprador, no_interesado
    etapa_venta: Optional[str] = None
    notas: Optional[str] = None


class ClienteCreate(ClienteBase):
    pass


class ClienteOut(ClienteBase):
    id: int

    class Config:
        from_attributes = True


# ---------- Propiedad ----------
class PropiedadBase(BaseModel):
    codigo: Optional[str] = None
    direccion: str
    ciudad: Optional[str] = None
    provincia: Optional[str] = None
    tipo: str
    modalidad: Optional[str] = "alquiler"
    estado: Optional[str] = "disponible"
    superficie_m2: Optional[float] = None
    ambientes: Optional[int] = None
    descripcion: Optional[str] = None
    precio_alquiler: Optional[float] = 0
    precio_venta: Optional[float] = 0
    expensas: Optional[float] = 0
    impuesto_inmobiliario: Optional[float] = 0
    tasa_municipal: Optional[float] = 0
    tokko_id: Optional[str] = None
    propietario_id: Optional[int] = None
    # Padrón municipal (Santa Rosa). Opcional.
    numero_referencia: Optional[str] = None


class PropiedadCreate(PropiedadBase):
    pass


class PropiedadOut(PropiedadBase):
    id: int
    propietario_nombre: Optional[str] = None
    tasa_consultada_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- Contrato ----------
class ContratoBase(BaseModel):
    codigo: Optional[str] = None
    tipo: str
    estado: Optional[str] = "borrador"
    propiedad_id: int
    inquilino_id: Optional[int] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    monto_inicial: Optional[float] = 0
    deposito: Optional[float] = 0
    indice_ajuste: Optional[str] = "ipc"
    periodicidad_meses: Optional[int] = 3
    porcentaje_fijo: Optional[float] = 0
    comision_porc: Optional[float] = 0
    notas: Optional[str] = None


class ContratoCreate(ContratoBase):
    pass


class ContratoOut(ContratoBase):
    id: int
    archivo_nombre: Optional[str] = None
    archivo_subido_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- Calculadora ----------
class CalculoIn(BaseModel):
    direccion: Optional[str] = None
    propiedad_id: Optional[int] = None
    fecha: Optional[date] = None  # fecha objetivo del cálculo


class CalculoOut(BaseModel):
    propiedad: dict
    contrato: Optional[dict] = None
    base_alquiler: float
    factor_ajuste: float
    alquiler_actualizado: float
    expensas: float
    impuesto_inmobiliario: float
    tasa_municipal: float
    total_mensual: float
    detalle: dict


# ---------- Refacciones ----------
class RefaccionBase(BaseModel):
    propiedad_id: int
    contrato_id: Optional[int] = None
    fecha: Optional[date] = None
    descripcion: str
    monto: float
    pagador: Optional[str] = "inquilino"   # inquilino | propietario
    estado: Optional[str] = "pendiente"    # pendiente | aplicada | cancelada
    notas: Optional[str] = None


class RefaccionCreate(RefaccionBase):
    pass


class RefaccionOut(RefaccionBase):
    id: int
    pago_id: Optional[int] = None
    propiedad_direccion: Optional[str] = None
    contrato_codigo: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
