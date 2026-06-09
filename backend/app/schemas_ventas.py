"""Schemas Pydantic del módulo VENTAS (aislado)."""
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel


class _Cfg:
    from_attributes = True


# ───────────── Vendedor ─────────────
class VendedorOut(BaseModel):
    id: int
    user_id: int
    nombre: str
    es_admin: bool
    activo: bool
    comision_default_pct: Optional[float] = None
    notif_matches_activa: bool
    hora_notif_matches: Optional[str] = None
    class Config(_Cfg): ...


class VendedorUpdate(BaseModel):
    nombre: Optional[str] = None
    activo: Optional[bool] = None
    comision_default_pct: Optional[float] = None
    notif_matches_activa: Optional[bool] = None
    hora_notif_matches: Optional[str] = None


# ───────────── Cliente + Notas ─────────────
class ClienteNotaOut(BaseModel):
    id: int
    cliente_id: int
    vendedor_id: Optional[int] = None
    texto: str
    origen: str
    created_at: datetime
    class Config(_Cfg): ...


class ClienteNotaCreate(BaseModel):
    texto: str
    origen: str = "web"


class ClienteCreate(BaseModel):
    nombre: str
    telefono: Optional[str] = None
    email: Optional[str] = None
    origen: Optional[str] = None
    observaciones: Optional[str] = None


class ClienteOut(BaseModel):
    id: int
    vendedor_id: Optional[int] = None
    nombre: str
    telefono: Optional[str] = None
    email: Optional[str] = None
    origen: Optional[str] = None
    observaciones: Optional[str] = None
    es_operado: bool
    created_at: datetime
    notas: List[ClienteNotaOut] = []
    class Config(_Cfg): ...


# ───────────── Propiedad ─────────────
class PropiedadCreate(BaseModel):
    titulo: Optional[str] = None
    tipo: str = "casa"
    estado: str = "disponible"
    fuente: str = "propia"
    direccion: Optional[str] = None
    ciudad: Optional[str] = None
    barrio_id: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    precio_usd: Optional[float] = None
    superficie_m2: Optional[float] = None
    dormitorios: Optional[int] = None
    banos: Optional[int] = None
    antiguedad_anios: Optional[int] = None
    descripcion: Optional[str] = None
    apreciacion: Optional[str] = None
    link_externo: Optional[str] = None
    inmobiliaria: Optional[str] = None
    contacto_id: Optional[int] = None


class PropiedadOut(PropiedadCreate):
    id: int
    cargada_por: Optional[int] = None
    created_at: datetime
    class Config(_Cfg): ...


# ───────────── Pedido ─────────────
class PedidoCreate(BaseModel):
    cliente_id: int
    estado: str = "nuevo"
    prioridad: str = "media"
    tipo: Optional[str] = None
    zona: Optional[str] = None
    barrio_id: Optional[int] = None
    precio_min_usd: Optional[float] = None
    precio_max_usd: Optional[float] = None
    dormitorios_min: Optional[int] = None
    banos_min: Optional[int] = None
    superficie_min_m2: Optional[float] = None
    detalle: Optional[str] = None


class PedidoUpdate(BaseModel):
    estado: Optional[str] = None
    prioridad: Optional[str] = None
    tipo: Optional[str] = None
    zona: Optional[str] = None
    barrio_id: Optional[int] = None
    precio_min_usd: Optional[float] = None
    precio_max_usd: Optional[float] = None
    dormitorios_min: Optional[int] = None
    banos_min: Optional[int] = None
    superficie_min_m2: Optional[float] = None
    detalle: Optional[str] = None
    orden_kanban: Optional[int] = None


class PedidoOut(BaseModel):
    id: int
    cliente_id: int
    vendedor_id: Optional[int] = None
    estado: str
    prioridad: str
    tipo: Optional[str] = None
    zona: Optional[str] = None
    barrio_id: Optional[int] = None
    precio_min_usd: Optional[float] = None
    precio_max_usd: Optional[float] = None
    dormitorios_min: Optional[int] = None
    banos_min: Optional[int] = None
    superficie_min_m2: Optional[float] = None
    detalle: Optional[str] = None
    orden_kanban: int
    created_at: datetime
    class Config(_Cfg): ...


class KanbanMove(BaseModel):
    estado: str
    orden_kanban: int = 0


# ───────────── Oferta ─────────────
class OfertaCreate(BaseModel):
    propiedad_id: int
    cliente_id: Optional[int] = None
    pedido_id: Optional[int] = None
    monto_usd: float
    tipo: str = "oferta"
    parte: str = "comprador"
    responde_a_id: Optional[int] = None
    nota: Optional[str] = None


class OfertaOut(BaseModel):
    id: int
    propiedad_id: int
    cliente_id: Optional[int] = None
    pedido_id: Optional[int] = None
    vendedor_id: Optional[int] = None
    monto_usd: float
    tipo: str
    parte: str
    estado: str
    responde_a_id: Optional[int] = None
    nota: Optional[str] = None
    created_at: datetime
    class Config(_Cfg): ...


# ───────────── Operación ─────────────
class OperacionCreate(BaseModel):
    propiedad_id: Optional[int] = None
    cliente_id: Optional[int] = None
    pedido_id: Optional[int] = None
    estado: str = "abierta"
    monto_cierre_usd: Optional[float] = None
    fecha_cierre: Optional[date] = None
    comision_pct: Optional[float] = None        # si viene, es carga manual
    comision_monto_usd: Optional[float] = None
    notas: Optional[str] = None


class OperacionOut(BaseModel):
    id: int
    propiedad_id: Optional[int] = None
    cliente_id: Optional[int] = None
    pedido_id: Optional[int] = None
    vendedor_id: Optional[int] = None
    estado: str
    monto_cierre_usd: Optional[float] = None
    fecha_cierre: Optional[date] = None
    comision_pct: Optional[float] = None
    comision_monto_usd: Optional[float] = None
    comision_manual: bool
    notas: Optional[str] = None
    created_at: datetime
    class Config(_Cfg): ...


# ───────────── Contacto ─────────────
class ContactoCreate(BaseModel):
    nombre: str
    tipo: str = "colega"
    telefono: Optional[str] = None
    email: Optional[str] = None
    empresa: Optional[str] = None
    notas: Optional[str] = None


class ContactoOut(ContactoCreate):
    id: int
    vendedor_id: int
    created_at: datetime
    class Config(_Cfg): ...


# ───────────── Barrio ─────────────
class BarrioCreate(BaseModel):
    nombre: str
    ciudad: Optional[str] = None
    poligono_geojson: Optional[str] = None
    color: Optional[str] = "#B8893A"


class BarrioOut(BarrioCreate):
    id: int
    class Config(_Cfg): ...


# ───────────── Comisión config (Mod #4) ─────────────
class ComisionConfigCreate(BaseModel):
    vendedor_id: int
    tipo: Optional[str] = None   # null = aplica a todos los tipos
    comision_pct: float


class ComisionConfigOut(BaseModel):
    id: int
    vendedor_id: int
    tipo: Optional[str] = None
    comision_pct: float
    class Config(_Cfg): ...


# ───────────── Valor m² referencia (Mod #1 fallback) ─────────────
class ValorM2Create(BaseModel):
    barrio_id: int
    tipo: Optional[str] = None
    valor_m2_usd: float


class ValorM2Out(BaseModel):
    id: int
    barrio_id: int
    tipo: Optional[str] = None
    valor_m2_usd: float
    class Config(_Cfg): ...


# ───────────── Vincular propiedad ↔ pedido ─────────────
class PedidoPropCreate(BaseModel):
    propiedad_id: int
    estado: str = "sugerida"     # sugerida | mostrada | descartada
    nota: Optional[str] = None


class PedidoPropOut(BaseModel):
    id: int
    pedido_id: int
    propiedad_id: int
    estado: str
    nota: Optional[str] = None
    created_at: datetime
    class Config(_Cfg): ...


# ───────────── Geocoding dirección → barrio (Mod #5) ─────────────
class GeocodeRequest(BaseModel):
    direccion: str
    ciudad: Optional[str] = None


class GeocodeOut(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None
    barrio_id: Optional[int] = None
    barrio_nombre: Optional[str] = None
    fuente: str   # nominatim | manual | sin_resultado


# ───────────── Tasación ─────────────
class TasacionRequest(BaseModel):
    tipo: str = "casa"
    barrio_id: Optional[int] = None
    direccion: Optional[str] = None
    superficie_m2: float
    dormitorios: Optional[int] = None
    banos: Optional[int] = None
    antiguedad_anios: Optional[int] = None
    estado_conservacion: Optional[str] = "bueno"   # nuevo|bueno|a_refaccionar


class TasacionOut(BaseModel):
    id: int
    tipo: str
    barrio_id: Optional[int] = None
    direccion: Optional[str] = None
    superficie_m2: Optional[float] = None
    valor_m2_usado: Optional[float] = None
    valor_min_usd: Optional[float] = None
    valor_medio_usd: Optional[float] = None
    valor_max_usd: Optional[float] = None
    confianza: Optional[str] = None
    metodo: Optional[str] = None
    comparables_json: Optional[str] = None
    informe_texto: Optional[str] = None
    created_at: datetime
    class Config(_Cfg): ...
