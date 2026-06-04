from datetime import datetime, date
from typing import Optional, List
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
    # Legacy: propietario principal. Si se manda solo este, se mappea
    # automáticamente a la tabla pivote como es_principal=True.
    propietario_id: Optional[int] = None
    # Nuevo: lista de co-propietarios. Cada uno: {cliente_id, porcentaje?}.
    # Si todos los porcentajes son null/0, se asume división equitativa.
    # Si se manda esta lista, sobreescribe la pivote completa.
    propietarios: Optional[list[dict]] = None
    # Padrón municipal (Santa Rosa). Opcional.
    numero_referencia: Optional[str] = None


class PropiedadCreate(PropiedadBase):
    pass


class PropiedadOut(PropiedadBase):
    id: int
    propietario_nombre: Optional[str] = None
    # Lista derivada de la pivote: [{cliente_id, nombre, porcentaje, es_principal}].
    # Si solo hay 1, viene esa entrada (consistente con flujo nuevo).
    propietarios_lista: Optional[list[dict]] = None
    tasa_consultada_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- Contrato ----------
class ContratoInquilinoIn(BaseModel):
    """Un firmante del contrato. Puede ser titular o co-firmante.

    Permite pasar `cliente_id` (referencia a Cliente ya existente) o crear
    uno nuevo enviando los datos completos (nombre, apellido, documento, etc.)
    desde el frontend — en cuyo caso `cliente_id` queda en None y el router
    crea el Cliente.
    """
    cliente_id: Optional[int] = None
    es_principal: Optional[bool] = False
    rol: Optional[str] = None  # 'inquilino', 'co_inquilino', 'garante', etc.

    # Datos para crear un Cliente nuevo si cliente_id es None:
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    razon_social: Optional[str] = None
    documento: Optional[str] = None
    tipo_documento: Optional[str] = None
    nacionalidad: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    notas: Optional[str] = None


class ContratoBase(BaseModel):
    codigo: Optional[str] = None
    tipo: str
    estado: Optional[str] = "borrador"
    propiedad_id: int
    # Inquilino principal (legacy / single). Por compat con la API anterior.
    # Si se mandó `inquilinos` (lista), `inquilino_id` se setea automático al
    # cliente marcado como principal de esa lista.
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
    # Lista opcional de inquilinos firmantes. Si viene, reemplaza el
    # `inquilino_id` single como fuente de verdad.
    inquilinos: Optional[List[ContratoInquilinoIn]] = None


class ContratoOut(ContratoBase):
    id: int
    archivo_nombre: Optional[str] = None
    archivo_subido_at: Optional[datetime] = None
    archivado: Optional[bool] = False
    fecha_archivado: Optional[datetime] = None
    # Lista completa de firmantes — siempre presente en respuestas.
    # Cada item: {id, cliente_id, nombre, apellido, documento, email,
    #             es_principal, rol}
    inquilinos_lista: Optional[List[dict]] = None

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


# ---------- Historial de acciones ----------
class AccionHistorialOut(BaseModel):
    id: int
    created_at: datetime
    user_id: Optional[int] = None
    user_nombre: Optional[str] = None
    entidad: str
    entidad_id: Optional[int] = None
    accion: str
    descripcion: str
    revertible: bool
    revertida: bool
    revertida_at: Optional[datetime] = None
    revertida_by_id: Optional[int] = None
    revertida_motivo: Optional[str] = None

    class Config:
        from_attributes = True


class AccionHistorialDetalle(AccionHistorialOut):
    """Igual que AccionHistorialOut pero incluye los snapshots completos."""
    snapshot_antes: Optional[dict] = None
    snapshot_despues: Optional[dict] = None


class RevertirAccionIn(BaseModel):
    motivo: Optional[str] = None
