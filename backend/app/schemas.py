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


class PropiedadCreate(PropiedadBase):
    pass


class PropiedadOut(PropiedadBase):
    id: int

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
