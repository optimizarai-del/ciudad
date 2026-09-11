"""
API externa del módulo Ventas — acceso por API key (sin login web).

Dos routers:
  · router (JWT): gestión de las API keys del usuario logueado.
      GET/POST/DELETE  /api/ventas-crm/api-keys
  · router_ext (X-API-Key): endpoints consumibles por terceros.
      GET/POST  /api/externo/clientes

Los clientes creados por la API se escriben DIRECTO en la base de datos
(Supabase en producción) a través de los modelos de la app —con su validación
y aislamiento— y quedan atribuidos al VENDEDOR dueño de la key (vendedor_id).
El secreto de la key nunca se guarda en claro: se guarda su hash (sha256) y el
secreto se muestra UNA sola vez al generarla.
"""
import hashlib
import secrets as _secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models, models_ventas as mv
from app.routers.ventas_crm import get_vendedor

router = APIRouter(prefix="/api/ventas-crm/api-keys", tags=["ventas-api-keys"])
router_ext = APIRouter(prefix="/api/externo", tags=["ventas-externo"])

_PREFIJO = "cvk_"   # ciudad-ventas-key


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ═══════════════ Gestión de keys (autenticado por JWT) ═══════════════

class _KeyIn(BaseModel):
    nombre: Optional[str] = None


@router.get("")
def listar_keys(db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_vendedor(db, user)  # garantiza acceso al módulo de Ventas
    ks = (db.query(mv.VentasApiKey)
          .filter(mv.VentasApiKey.user_id == user.id)
          .order_by(mv.VentasApiKey.id.desc()).all())
    return [{
        "id": k.id, "nombre": k.nombre, "prefijo": k.prefijo, "activa": k.activa,
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        "created_at": k.created_at.isoformat() if k.created_at else None,
    } for k in ks]


@router.post("")
def crear_key(data: _KeyIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    raw = _PREFIJO + _secrets.token_urlsafe(32)
    k = mv.VentasApiKey(
        user_id=user.id, vendedor_id=v.id, is_demo=bool(v.is_demo),
        nombre=(data.nombre or "API key"), prefijo=raw[:12],
        key_hash=_hash(raw), activa=True,
    )
    db.add(k); db.commit(); db.refresh(k)
    # El secreto (`api_key`) se devuelve UNA sola vez; después solo queda el hash.
    return {
        "id": k.id, "nombre": k.nombre, "prefijo": k.prefijo, "api_key": raw,
        "aviso": "Guardá esta clave ahora: por seguridad no se vuelve a mostrar.",
    }


@router.delete("/{kid}")
def revocar_key(kid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    k = db.query(mv.VentasApiKey).filter_by(id=kid, user_id=user.id).first()
    if not k:
        raise HTTPException(404, "API key no encontrada")
    k.activa = False
    db.commit()
    return {"ok": True}


# ═══════════════ Auth por API key + endpoints externos ═══════════════

def get_api_context(request: Request, db: Session = Depends(get_db)) -> dict:
    """Resuelve la API key del header `X-API-Key` (o `?api_key=`) y devuelve el
    contexto del dueño (usuario + vendedor + workspace demo)."""
    raw = (request.headers.get("X-API-Key") or request.query_params.get("api_key") or "").strip()
    if not raw:
        raise HTTPException(401, "Falta la API key (header X-API-Key)")
    k = db.query(mv.VentasApiKey).filter_by(key_hash=_hash(raw), activa=True).first()
    if not k:
        raise HTTPException(401, "API key inválida o revocada")
    user = db.query(models.User).filter_by(id=k.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(401, "Usuario inactivo")
    # Resolver el vendedor dueño (auto-provisiona si hiciera falta) para que los
    # clientes creados por la API queden SIEMPRE atribuidos a un vendedor válido.
    vend = db.query(mv.VentasVendedor).filter_by(id=k.vendedor_id).first() if k.vendedor_id else None
    if not vend:
        vend = get_vendedor(db, user)
        k.vendedor_id = vend.id
    k.last_used_at = datetime.utcnow()
    db.commit()
    return {"user": user, "key": k, "vendedor_id": vend.id, "is_demo": bool(vend.is_demo)}


class _ClienteExtIn(BaseModel):
    nombre: str
    telefono: Optional[str] = None
    email: Optional[str] = None
    origen: Optional[str] = None
    observaciones: Optional[str] = None


def _cliente_out(c: "mv.VentasCliente") -> dict:
    return {
        "id": c.id, "nombre": c.nombre, "telefono": c.telefono, "email": c.email,
        "origen": c.origen, "etapa": c.etapa,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router_ext.get("/clientes")
def externo_listar_clientes(q: Optional[str] = None, limit: int = Query(100, le=500),
                            ctx=Depends(get_api_context), db: Session = Depends(get_db)):
    """Lista los clientes del vendedor dueño de la API key."""
    query = (db.query(mv.VentasCliente)
             .filter(mv.VentasCliente.vendedor_id == ctx["vendedor_id"],
                     mv.VentasCliente.is_demo == ctx["is_demo"]))
    if q:
        like = f"%{q}%"
        query = query.filter((mv.VentasCliente.nombre.ilike(like)) |
                             (mv.VentasCliente.telefono.ilike(like)) |
                             (mv.VentasCliente.email.ilike(like)))
    rows = query.order_by(mv.VentasCliente.id.desc()).limit(limit).all()
    return [_cliente_out(c) for c in rows]


@router_ext.post("/clientes")
def externo_crear_cliente(data: _ClienteExtIn, ctx=Depends(get_api_context),
                          db: Session = Depends(get_db)):
    """Crea un cliente en la base (Supabase en producción) atribuido al vendedor
    dueño de la API key."""
    if not (data.nombre or "").strip():
        raise HTTPException(400, "El nombre es obligatorio")
    obj = mv.VentasCliente(
        nombre=data.nombre.strip(), telefono=data.telefono, email=data.email,
        origen=(data.origen or "api"), observaciones=data.observaciones,
        vendedor_id=ctx["vendedor_id"], is_demo=ctx["is_demo"],
        etapa_desde=datetime.utcnow(),
    )
    db.add(obj); db.commit(); db.refresh(obj)
    return {**_cliente_out(obj), "creado": True}
