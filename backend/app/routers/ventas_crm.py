"""
Módulo VENTAS — CRM aislado. Router CRUD bajo /api/ventas-crm.

Aislamiento:
- Tablas dedicadas ventas_* (ver models_ventas.py).
- Scoping por vendedor: un vendedor ve solo lo suyo; el admin ve todo.
- Auth compartida (users) pero perfil propio del módulo (ventas_vendedores).

El router legacy ventas_router.py (/api/ventas/*) queda como compatibilidad
para las pantallas viejas que leen de las tablas compartidas.
"""
import json
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models, models_ventas as mv, schemas_ventas as sv
from app.services.ventas_tasacion import tasar
from app.services import ventas_geo, ventas_matching, ventas_tareas

router = APIRouter(prefix="/api/ventas-crm", tags=["ventas-crm"])

_ESTADOS_VINCULO = ("sugerida", "mostrada", "descartada")


# ───────────────────── Helpers de vendedor / scoping ─────────────────────

def get_vendedor(db: Session, user) -> mv.VentasVendedor:
    """Devuelve (creando si hace falta) el perfil de ventas del usuario.

    Auto-provisión: cualquier usuario con rol admin/gerencia/ventas que entra
    al módulo obtiene un perfil. admin/gerencia → es_admin=True.
    """
    v = db.query(mv.VentasVendedor).filter_by(user_id=user.id).first()
    if v:
        return v
    role = user.role.value if hasattr(user.role, "value") else user.role
    if role not in ("admin", "gerencia", "ventas", "ventas_admin"):
        raise HTTPException(403, "No tenés acceso al módulo de Ventas")
    es_admin = role in ("admin", "gerencia", "ventas_admin")
    v = mv.VentasVendedor(
        user_id=user.id,
        nombre=user.nombre,
        es_admin=es_admin,
    )
    db.add(v); db.commit(); db.refresh(v)
    return v


def _audit(db, vendedor, entidad, entidad_id, accion, detalle=None):
    db.add(mv.VentasAuditLog(
        vendedor_id=vendedor.id, entidad=entidad, entidad_id=entidad_id,
        accion=accion, detalle=json.dumps(detalle, ensure_ascii=False, default=str) if detalle else None,
    ))


def _scope(query, model, vendedor):
    """Filtra por vendedor salvo que sea admin (ve todo)."""
    if vendedor.es_admin:
        return query
    return query.filter(model.vendedor_id == vendedor.id)


def _enum(EnumCls, value, field):
    if value is None:
        return None
    try:
        return EnumCls(value)
    except ValueError:
        ops = ", ".join(e.value for e in EnumCls)
        raise HTTPException(400, f"{field} inválido: '{value}'. Opciones: {ops}")


# ───────────────────── Vendedores ─────────────────────

@router.get("/me", response_model=sv.VendedorOut)
def me(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return get_vendedor(db, user)


@router.get("/vendedores", response_model=List[sv.VendedorOut])
def listar_vendedores(db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    if not v.es_admin:
        return [v]
    return db.query(mv.VentasVendedor).order_by(mv.VentasVendedor.id).all()


@router.patch("/vendedores/{vid}", response_model=sv.VendedorOut)
def editar_vendedor(vid: int, data: sv.VendedorUpdate,
                    db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    obj = db.query(mv.VentasVendedor).filter_by(id=vid).first()
    if not obj:
        raise HTTPException(404, "Vendedor no encontrado")
    # Un vendedor solo se edita a sí mismo; el admin a cualquiera
    if not v.es_admin and obj.id != v.id:
        raise HTTPException(403, "No podés editar a otro vendedor")
    for k, val in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, val)
    db.commit(); db.refresh(obj)
    return obj


# ───────────────────── Clientes + Notas ─────────────────────

@router.get("/clientes", response_model=List[sv.ClienteOut])
def listar_clientes(operados: Optional[bool] = None, q: Optional[str] = None,
                    skip: int = 0, limit: int = Query(200, le=500),
                    db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    query = _scope(db.query(mv.VentasCliente), mv.VentasCliente, v)
    if operados is not None:
        query = query.filter(mv.VentasCliente.es_operado == operados)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (mv.VentasCliente.nombre.ilike(like)) |
            (mv.VentasCliente.email.ilike(like)) |
            (mv.VentasCliente.telefono.ilike(like)) |
            (mv.VentasCliente.origen.ilike(like))
        )
    return query.order_by(mv.VentasCliente.id.desc()).offset(skip).limit(limit).all()


@router.post("/clientes", response_model=sv.ClienteOut)
def crear_cliente(data: sv.ClienteCreate,
                  db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    obj = mv.VentasCliente(**data.model_dump(), vendedor_id=v.id)
    db.add(obj); db.flush()
    _audit(db, v, "ventas_clientes", obj.id, mv.AuditAccion.create, data.model_dump())
    db.commit(); db.refresh(obj)
    return obj


@router.patch("/clientes/{cid}", response_model=sv.ClienteOut)
def editar_cliente(cid: int, data: sv.ClienteCreate,
                   db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    obj = _scope(db.query(mv.VentasCliente), mv.VentasCliente, v).filter_by(id=cid).first()
    if not obj:
        raise HTTPException(404, "Cliente no encontrado")
    for k, val in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, val)
    _audit(db, v, "ventas_clientes", obj.id, mv.AuditAccion.update, data.model_dump(exclude_unset=True))
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/clientes/{cid}")
def eliminar_cliente(cid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    obj = _scope(db.query(mv.VentasCliente), mv.VentasCliente, v).filter_by(id=cid).first()
    if not obj:
        raise HTTPException(404, "Cliente no encontrado")
    # Limpiar dependientes (FK sin cascade declarado). Los pedidos del cliente
    # arrastran sus matches/vínculos/ofertas.
    pedido_ids = [p.id for p in db.query(mv.VentasPedido).filter_by(cliente_id=cid).all()]
    if pedido_ids:
        db.query(mv.VentasMatch).filter(mv.VentasMatch.pedido_id.in_(pedido_ids)).delete(synchronize_session=False)
        db.query(mv.VentasPedidoPropiedad).filter(mv.VentasPedidoPropiedad.pedido_id.in_(pedido_ids)).delete(synchronize_session=False)
        # Desreferenciar pedido_id en ofertas/operaciones que apuntan a esos
        # pedidos (antes de borrarlos), si no quedarían colgando en Postgres.
        db.query(mv.VentasOferta).filter(mv.VentasOferta.pedido_id.in_(pedido_ids)).update({"pedido_id": None}, synchronize_session=False)
        db.query(mv.VentasOperacion).filter(mv.VentasOperacion.pedido_id.in_(pedido_ids)).update({"pedido_id": None}, synchronize_session=False)
    db.query(mv.VentasOferta).filter_by(cliente_id=cid).update({"cliente_id": None}, synchronize_session=False)
    db.query(mv.VentasPedido).filter_by(cliente_id=cid).delete(synchronize_session=False)
    db.query(mv.VentasTarea).filter_by(cliente_id=cid).update({"cliente_id": None}, synchronize_session=False)
    db.query(mv.VentasOperacion).filter_by(cliente_id=cid).update({"cliente_id": None}, synchronize_session=False)
    _audit(db, v, "ventas_clientes", cid, mv.AuditAccion.delete)
    db.delete(obj); db.commit()
    return {"ok": True}


@router.post("/clientes/{cid}/notas", response_model=sv.ClienteNotaOut)
def agregar_nota(cid: int, data: sv.ClienteNotaCreate,
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Mod #6: agrega una nota al hilo del cliente."""
    v = get_vendedor(db, user)
    cli = _scope(db.query(mv.VentasCliente), mv.VentasCliente, v).filter_by(id=cid).first()
    if not cli:
        raise HTTPException(404, "Cliente no encontrado")
    nota = mv.VentasClienteNota(cliente_id=cid, vendedor_id=v.id,
                                texto=data.texto, origen=data.origen)
    db.add(nota); db.commit(); db.refresh(nota)
    return nota


@router.get("/clientes/{cid}/notas", response_model=List[sv.ClienteNotaOut])
def listar_notas(cid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    cli = _scope(db.query(mv.VentasCliente), mv.VentasCliente, v).filter_by(id=cid).first()
    if not cli:
        raise HTTPException(404, "Cliente no encontrado")
    return (db.query(mv.VentasClienteNota).filter_by(cliente_id=cid)
            .order_by(mv.VentasClienteNota.created_at.desc()).all())


@router.delete("/clientes/{cid}/notas/{nid}")
def eliminar_nota(cid: int, nid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    cli = _scope(db.query(mv.VentasCliente), mv.VentasCliente, v).filter_by(id=cid).first()
    if not cli:
        raise HTTPException(404, "Cliente no encontrado")
    nota = db.query(mv.VentasClienteNota).filter_by(id=nid, cliente_id=cid).first()
    if not nota:
        raise HTTPException(404, "Nota no encontrada")
    db.delete(nota); db.commit()
    return {"ok": True}


def _fmt_usd(n):
    return f"USD {n:,.0f}".replace(",", ".") if n else "—"


@router.get("/clientes/{cid}/ficha")
def ficha_cliente(cid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Ficha 360° del cliente para la tarjeta del CRM: info relevante, última
    interacción, acciones recomendadas e historial unificado de acciones."""
    from datetime import datetime
    v = get_vendedor(db, user)
    cli = _scope(db.query(mv.VentasCliente), mv.VentasCliente, v).filter_by(id=cid).first()
    if not cli:
        raise HTTPException(404, "Cliente no encontrado")

    notas = db.query(mv.VentasClienteNota).filter_by(cliente_id=cid).all()
    pedidos = db.query(mv.VentasPedido).filter_by(cliente_id=cid).all()
    ops = db.query(mv.VentasOperacion).filter_by(cliente_id=cid).all()
    ofertas = db.query(mv.VentasOferta).filter_by(cliente_id=cid).all()

    # Historial unificado (timeline)
    timeline = []
    for n in notas:
        timeline.append({"id": n.id, "tipo": "nota", "texto": n.texto,
                         "fecha": n.created_at, "origen": n.origen})
    for p in pedidos:
        est = p.estado.value if hasattr(p.estado, "value") else p.estado
        desc = " ".join(x for x in [p.tipo.value if p.tipo and hasattr(p.tipo, "value") else None, p.zona] if x)
        timeline.append({"id": None, "tipo": "pedido", "texto": f"Pedido [{est}] {desc}".strip(),
                         "fecha": p.created_at, "origen": None})
    for o in ops:
        est = o.estado.value if hasattr(o.estado, "value") else o.estado
        timeline.append({"id": None, "tipo": "operacion", "texto": f"Operación {est} · {_fmt_usd(o.monto_cierre_usd)}",
                         "fecha": o.created_at, "origen": None})
    for of in ofertas:
        t = of.tipo.value if hasattr(of.tipo, "value") else of.tipo
        timeline.append({"id": None, "tipo": "oferta", "texto": f"{t.capitalize()} {_fmt_usd(of.monto_usd)}",
                         "fecha": of.created_at, "origen": None})

    timeline = [t for t in timeline if t["fecha"]]
    timeline.sort(key=lambda t: t["fecha"], reverse=True)
    ultima = timeline[0]["fecha"] if timeline else cli.created_at
    dias_sin_contacto = (datetime.utcnow() - ultima).days if ultima else None

    # Pedidos activos (no cerrados/perdidos)
    activos = [p for p in pedidos
               if (p.estado.value if hasattr(p.estado, "value") else p.estado) not in ("cerrado", "perdido")]
    estados_activos = {(p.estado.value if hasattr(p.estado, "value") else p.estado) for p in activos}

    # Acciones recomendadas (reglas simples)
    recs = []
    if not notas:
        recs.append("Registrar el primer contacto y dejar una nota.")
    if "nuevo" in estados_activos:
        recs.append("Contactar al cliente — tiene un pedido sin contactar.")
    if "esperando_respuesta" in estados_activos:
        recs.append("Hacer seguimiento: el cliente está esperando respuesta.")
    if "negociando" in estados_activos:
        recs.append("Avanzar la negociación o registrar una oferta.")
    if "en_seguimiento" in estados_activos:
        recs.append("Continuar el seguimiento periódico.")
    if cli.es_operado:
        recs.append("Agendar seguimiento post-venta.")
    if dias_sin_contacto is not None and dias_sin_contacto >= 14 and activos:
        recs.append(f"Pasaron {dias_sin_contacto} días sin contacto — conviene retomar.")
    if not recs:
        recs.append("Sin acciones pendientes. Mantené el seguimiento.")

    # Rango de presupuesto buscado (de los pedidos activos)
    maxs = [p.precio_max_usd for p in activos if p.precio_max_usd]
    presupuesto = _fmt_usd(max(maxs)) if maxs else None

    return {
        "cliente": {
            "id": cli.id, "nombre": cli.nombre, "telefono": cli.telefono,
            "email": cli.email, "origen": cli.origen, "observaciones": cli.observaciones,
            "es_operado": cli.es_operado,
            "cliente_desde": cli.created_at.isoformat() if cli.created_at else None,
        },
        "ultima_interaccion": ultima.isoformat() if ultima else None,
        "dias_sin_contacto": dias_sin_contacto,
        "info": {
            "pedidos_activos": len(activos),
            "pedidos_total": len(pedidos),
            "operaciones": len(ops),
            "presupuesto_max": presupuesto,
            "notas": len(notas),
        },
        "recomendaciones": recs,
        "historial": [
            {"id": t.get("id"), "tipo": t["tipo"], "texto": t["texto"], "origen": t["origen"],
             "fecha": t["fecha"].isoformat()}
            for t in timeline
        ],
    }


# ───────────────────── Propiedades (catálogo aislado) ─────────────────────

@router.get("/propiedades", response_model=List[sv.PropiedadOut])
def listar_propiedades(barrio_id: Optional[int] = None, tipo: Optional[str] = None,
                       estado: Optional[str] = None, q: Optional[str] = None,
                       skip: int = 0, limit: int = Query(200, le=500),
                       db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_vendedor(db, user)  # garantiza acceso
    query = db.query(mv.VentasPropiedad)
    if barrio_id is not None:
        query = query.filter(mv.VentasPropiedad.barrio_id == barrio_id)
    if tipo:
        query = query.filter(mv.VentasPropiedad.tipo == _enum(mv.VPropiedadTipo, tipo, "tipo"))
    if estado:
        query = query.filter(mv.VentasPropiedad.estado == _enum(mv.VPropiedadEstado, estado, "estado"))
    if q:
        like = f"%{q}%"
        query = query.filter(
            (mv.VentasPropiedad.direccion.ilike(like)) |
            (mv.VentasPropiedad.descripcion.ilike(like)) |
            (mv.VentasPropiedad.ciudad.ilike(like))
        )
    return query.order_by(mv.VentasPropiedad.id.desc()).offset(skip).limit(limit).all()


@router.post("/propiedades", response_model=sv.PropiedadOut)
def crear_propiedad(data: sv.PropiedadCreate,
                    db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    payload = data.model_dump()
    payload["tipo"] = _enum(mv.VPropiedadTipo, payload.get("tipo"), "tipo")
    payload["estado"] = _enum(mv.VPropiedadEstado, payload.get("estado"), "estado")
    payload["fuente"] = _enum(mv.VPropiedadFuente, payload.get("fuente"), "fuente")
    obj = mv.VentasPropiedad(**payload, cargada_por=v.id)
    # Auto-geocoding (Mod #5): si hay dirección y no se asignó barrio a mano,
    # intentar resolver lat/lng y barrio. Best-effort, no bloquea el alta.
    if obj.direccion and not obj.barrio_id:
        try:
            geo = ventas_geo.resolver(db, obj.direccion, obj.ciudad)
            obj.lat, obj.lng = geo["lat"], geo["lng"]
            obj.barrio_id = geo["barrio_id"]
        except Exception as e:
            print(f"[ventas_crm] geocoding propiedad fallback: {e}")
    db.add(obj); db.flush()
    _audit(db, v, "ventas_propiedades", obj.id, mv.AuditAccion.create, data.model_dump())
    try:
        ventas_matching.evaluar_propiedad(db, obj)
    except Exception as e:
        print(f"[ventas_crm] matching propiedad fallback: {e}")
    db.commit(); db.refresh(obj)
    return obj


@router.patch("/propiedades/{pid}", response_model=sv.PropiedadOut)
def editar_propiedad(pid: int, data: sv.PropiedadCreate,
                     db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    obj = db.query(mv.VentasPropiedad).filter_by(id=pid).first()
    if not obj:
        raise HTTPException(404, "Propiedad no encontrada")
    payload = data.model_dump(exclude_unset=True)
    if "tipo" in payload: payload["tipo"] = _enum(mv.VPropiedadTipo, payload["tipo"], "tipo")
    if "estado" in payload: payload["estado"] = _enum(mv.VPropiedadEstado, payload["estado"], "estado")
    if "fuente" in payload: payload["fuente"] = _enum(mv.VPropiedadFuente, payload["fuente"], "fuente")
    for k, val in payload.items():
        setattr(obj, k, val)
    _audit(db, v, "ventas_propiedades", pid, mv.AuditAccion.update, data.model_dump(exclude_unset=True))
    try:
        ventas_matching.evaluar_propiedad(db, obj)
    except Exception as e:
        print(f"[ventas_crm] matching propiedad fallback: {e}")
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/propiedades/{pid}")
def eliminar_propiedad(pid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    obj = db.query(mv.VentasPropiedad).filter_by(id=pid).first()
    if not obj:
        raise HTTPException(404, "Propiedad no encontrada")
    # Limpiar dependientes (FK sin cascade declarado)
    db.query(mv.VentasMatch).filter_by(propiedad_id=pid).delete(synchronize_session=False)
    db.query(mv.VentasPedidoPropiedad).filter_by(propiedad_id=pid).delete(synchronize_session=False)
    db.query(mv.VentasOferta).filter_by(propiedad_id=pid).delete(synchronize_session=False)
    db.query(mv.VentasOperacion).filter_by(propiedad_id=pid).update({"propiedad_id": None})
    _audit(db, v, "ventas_propiedades", pid, mv.AuditAccion.delete)
    db.delete(obj); db.commit()
    return {"ok": True}


# ───────────────────── Ofertas / Contraofertas (Mod #2) ─────────────────────

@router.get("/propiedades/{pid}/ofertas", response_model=List[sv.OfertaOut])
def listar_ofertas(pid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_vendedor(db, user)
    return (db.query(mv.VentasOferta).filter_by(propiedad_id=pid)
            .order_by(mv.VentasOferta.created_at.asc()).all())


@router.post("/ofertas", response_model=sv.OfertaOut)
def crear_oferta(data: sv.OfertaCreate,
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    payload = data.model_dump()
    payload["tipo"] = _enum(mv.OfertaTipo, payload.get("tipo"), "tipo")
    payload["parte"] = _enum(mv.OfertaParte, payload.get("parte"), "parte")
    obj = mv.VentasOferta(**payload, vendedor_id=v.id)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.patch("/ofertas/{oid}", response_model=sv.OfertaOut)
def cambiar_estado_oferta(oid: int, estado: str = Query(...),
                          db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    obj = db.query(mv.VentasOferta).filter_by(id=oid).first()
    if not obj:
        raise HTTPException(404, "Oferta no encontrada")
    if not v.es_admin and obj.vendedor_id != v.id:
        raise HTTPException(403, "No es tu oferta")
    obj.estado = _enum(mv.OfertaEstado, estado, "estado")
    db.commit(); db.refresh(obj)
    return obj


# ───────────────────── Pedidos + Kanban ─────────────────────

@router.get("/pedidos", response_model=List[sv.PedidoOut])
def listar_pedidos(estado: Optional[str] = None, cliente_id: Optional[int] = None,
                   prioridad: Optional[str] = None, skip: int = 0,
                   limit: int = Query(300, le=1000),
                   db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    q = _scope(db.query(mv.VentasPedido), mv.VentasPedido, v)
    if estado:
        q = q.filter(mv.VentasPedido.estado == _enum(mv.PedidoEstado, estado, "estado"))
    if prioridad:
        q = q.filter(mv.VentasPedido.prioridad == _enum(mv.PedidoPrioridad, prioridad, "prioridad"))
    if cliente_id:
        q = q.filter(mv.VentasPedido.cliente_id == cliente_id)
    return q.order_by(mv.VentasPedido.orden_kanban, mv.VentasPedido.id.desc()).offset(skip).limit(limit).all()


@router.post("/pedidos", response_model=sv.PedidoOut)
def crear_pedido(data: sv.PedidoCreate,
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    payload = data.model_dump()
    payload["estado"] = _enum(mv.PedidoEstado, payload.get("estado"), "estado")
    payload["prioridad"] = _enum(mv.PedidoPrioridad, payload.get("prioridad"), "prioridad")
    payload["tipo"] = _enum(mv.VPropiedadTipo, payload.get("tipo"), "tipo")
    obj = mv.VentasPedido(**payload, vendedor_id=v.id)
    db.add(obj); db.flush()
    _audit(db, v, "ventas_pedidos", obj.id, mv.AuditAccion.create, data.model_dump())
    try:
        ventas_matching.evaluar_pedido(db, obj)
    except Exception as e:
        print(f"[ventas_crm] matching pedido fallback: {e}")
    db.commit(); db.refresh(obj)
    return obj


@router.patch("/pedidos/{pid}", response_model=sv.PedidoOut)
def editar_pedido(pid: int, data: sv.PedidoUpdate,
                  db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    obj = _scope(db.query(mv.VentasPedido), mv.VentasPedido, v).filter_by(id=pid).first()
    if not obj:
        raise HTTPException(404, "Pedido no encontrado")
    payload = data.model_dump(exclude_unset=True)
    if "estado" in payload: payload["estado"] = _enum(mv.PedidoEstado, payload["estado"], "estado")
    if "prioridad" in payload: payload["prioridad"] = _enum(mv.PedidoPrioridad, payload["prioridad"], "prioridad")
    if "tipo" in payload: payload["tipo"] = _enum(mv.VPropiedadTipo, payload["tipo"], "tipo")
    for k, val in payload.items():
        setattr(obj, k, val)
    try:
        ventas_matching.evaluar_pedido(db, obj)
    except Exception as e:
        print(f"[ventas_crm] matching pedido fallback: {e}")
    db.commit(); db.refresh(obj)
    return obj


@router.patch("/pedidos/{pid}/mover", response_model=sv.PedidoOut)
def mover_pedido(pid: int, data: sv.KanbanMove,
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Drag-and-drop del kanban: cambia estado + posición."""
    v = get_vendedor(db, user)
    obj = _scope(db.query(mv.VentasPedido), mv.VentasPedido, v).filter_by(id=pid).first()
    if not obj:
        raise HTTPException(404, "Pedido no encontrado")
    obj.estado = _enum(mv.PedidoEstado, data.estado, "estado")
    obj.orden_kanban = data.orden_kanban
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/pedidos/{pid}")
def eliminar_pedido(pid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    obj = _scope(db.query(mv.VentasPedido), mv.VentasPedido, v).filter_by(id=pid).first()
    if not obj:
        raise HTTPException(404, "Pedido no encontrado")
    # Limpiar dependientes (sin cascade declarado → evitar IntegrityError en Postgres)
    db.query(mv.VentasMatch).filter_by(pedido_id=pid).delete(synchronize_session=False)
    db.query(mv.VentasPedidoPropiedad).filter_by(pedido_id=pid).delete(synchronize_session=False)
    db.query(mv.VentasOferta).filter(mv.VentasOferta.pedido_id == pid).update({"pedido_id": None}, synchronize_session=False)
    db.query(mv.VentasOperacion).filter(mv.VentasOperacion.pedido_id == pid).update({"pedido_id": None}, synchronize_session=False)
    _audit(db, v, "ventas_pedidos", pid, mv.AuditAccion.delete)
    db.delete(obj); db.commit()
    return {"ok": True}


# ───────────────────── Operaciones + Comisión (Mod #4) ─────────────────────

def _calcular_comision(db, vendedor_id, tipo_propiedad, monto):
    """Devuelve (pct, monto_comision) usando config por vendedor+tipo o el
    default del vendedor."""
    cfg = None
    if tipo_propiedad is not None:
        cfg = (db.query(mv.VentasComisionConfig)
               .filter_by(vendedor_id=vendedor_id, tipo=tipo_propiedad).first())
    if not cfg:
        cfg = (db.query(mv.VentasComisionConfig)
               .filter_by(vendedor_id=vendedor_id, tipo=None).first())
    if cfg:
        pct = cfg.comision_pct
    else:
        vend = db.query(mv.VentasVendedor).filter_by(id=vendedor_id).first()
        pct = vend.comision_default_pct if vend else 3.0
    monto_com = round((monto or 0) * pct / 100.0, 2)
    return pct, monto_com


@router.get("/operaciones", response_model=List[sv.OperacionOut])
def listar_operaciones(db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    return (_scope(db.query(mv.VentasOperacion), mv.VentasOperacion, v)
            .order_by(mv.VentasOperacion.id.desc()).all())


@router.post("/operaciones", response_model=sv.OperacionOut)
def crear_operacion(data: sv.OperacionCreate,
                    db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    payload = data.model_dump()
    payload["estado"] = _enum(mv.OperacionEstado, payload.get("estado"), "estado")

    manual = payload.get("comision_pct") is not None or payload.get("comision_monto_usd") is not None
    obj = mv.VentasOperacion(**payload, vendedor_id=v.id, comision_manual=manual)

    if not manual and obj.monto_cierre_usd:
        tipo_prop = None
        if obj.propiedad_id:
            prop = db.query(mv.VentasPropiedad).filter_by(id=obj.propiedad_id).first()
            tipo_prop = prop.tipo if prop else None
        pct, monto_com = _calcular_comision(db, v.id, tipo_prop, obj.monto_cierre_usd)
        obj.comision_pct = pct
        obj.comision_monto_usd = monto_com
    elif manual and obj.comision_pct is not None and obj.comision_monto_usd is None and obj.monto_cierre_usd:
        obj.comision_monto_usd = round(obj.monto_cierre_usd * obj.comision_pct / 100.0, 2)

    db.add(obj); db.flush()

    # Si la operación se cierra, marcar cliente como operado (grupo post-venta)
    if obj.estado in (mv.OperacionEstado.cerrada, mv.OperacionEstado.sena) and obj.cliente_id:
        cli = db.query(mv.VentasCliente).filter_by(id=obj.cliente_id).first()
        if cli:
            cli.es_operado = True

    # Post-venta (Fase 3): generar tareas de seguimiento si la operación cerró.
    if obj.estado == mv.OperacionEstado.cerrada:
        try:
            ventas_tareas.generar_tareas_postventa(db, obj)
        except Exception as e:
            print(f"[ventas_crm] tareas postventa fallback: {e}")

    _audit(db, v, "ventas_operaciones", obj.id, mv.AuditAccion.create, data.model_dump())
    db.commit(); db.refresh(obj)
    return obj


@router.patch("/operaciones/{oid}", response_model=sv.OperacionOut)
def editar_operacion(oid: int, data: sv.OperacionCreate,
                     db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    obj = _scope(db.query(mv.VentasOperacion), mv.VentasOperacion, v).filter_by(id=oid).first()
    if not obj:
        raise HTTPException(404, "Operación no encontrada")
    payload = data.model_dump(exclude_unset=True)
    if "estado" in payload:
        payload["estado"] = _enum(mv.OperacionEstado, payload["estado"], "estado")
    if "comision_pct" in payload or "comision_monto_usd" in payload:
        obj.comision_manual = True
    for k, val in payload.items():
        setattr(obj, k, val)

    # Recalcular comisión: automática si no es manual; si es manual y solo
    # vino el %, derivar el monto desde el monto de cierre.
    if not obj.comision_manual and obj.monto_cierre_usd:
        tipo_prop = None
        if obj.propiedad_id:
            prop = db.query(mv.VentasPropiedad).filter_by(id=obj.propiedad_id).first()
            tipo_prop = prop.tipo if prop else None
        pct, monto_com = _calcular_comision(db, obj.vendedor_id, tipo_prop, obj.monto_cierre_usd)
        obj.comision_pct = pct
        obj.comision_monto_usd = monto_com
    elif obj.comision_manual and obj.comision_pct is not None and obj.comision_monto_usd is None and obj.monto_cierre_usd:
        obj.comision_monto_usd = round(obj.monto_cierre_usd * obj.comision_pct / 100.0, 2)

    # Si la edición cierra la operación, replicar la lógica de cierre.
    if obj.estado in (mv.OperacionEstado.cerrada, mv.OperacionEstado.sena) and obj.cliente_id:
        cli = db.query(mv.VentasCliente).filter_by(id=obj.cliente_id).first()
        if cli:
            cli.es_operado = True
    if obj.estado == mv.OperacionEstado.cerrada:
        try:
            ventas_tareas.generar_tareas_postventa(db, obj)
        except Exception as e:
            print(f"[ventas_crm] tareas postventa (edit) fallback: {e}")

    _audit(db, v, "ventas_operaciones", obj.id, mv.AuditAccion.update, data.model_dump(exclude_unset=True))
    db.commit(); db.refresh(obj)
    return obj


# ───────────────────── Contactos (Mod #3) ─────────────────────

@router.get("/contactos", response_model=List[sv.ContactoOut])
def listar_contactos(vendedor_id: Optional[int] = None,
                     db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    q = db.query(mv.VentasContacto)
    if v.es_admin:
        if vendedor_id:
            q = q.filter(mv.VentasContacto.vendedor_id == vendedor_id)
    else:
        q = q.filter(mv.VentasContacto.vendedor_id == v.id)
    return q.order_by(mv.VentasContacto.nombre).all()


@router.post("/contactos", response_model=sv.ContactoOut)
def crear_contacto(data: sv.ContactoCreate,
                   db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    payload = data.model_dump()
    payload["tipo"] = _enum(mv.ContactoTipo, payload.get("tipo"), "tipo")
    obj = mv.VentasContacto(**payload, vendedor_id=v.id)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.patch("/contactos/{cid}", response_model=sv.ContactoOut)
def editar_contacto(cid: int, data: sv.ContactoCreate,
                    db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    q = db.query(mv.VentasContacto).filter_by(id=cid)
    obj = q.first()
    if not obj:
        raise HTTPException(404, "Contacto no encontrado")
    if not v.es_admin and obj.vendedor_id != v.id:
        raise HTTPException(403, "No es tu contacto")
    payload = data.model_dump(exclude_unset=True)
    if "tipo" in payload: payload["tipo"] = _enum(mv.ContactoTipo, payload["tipo"], "tipo")
    for k, val in payload.items():
        setattr(obj, k, val)
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/contactos/{cid}")
def eliminar_contacto(cid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    obj = db.query(mv.VentasContacto).filter_by(id=cid).first()
    if not obj:
        raise HTTPException(404, "Contacto no encontrado")
    if not v.es_admin and obj.vendedor_id != v.id:
        raise HTTPException(403, "No es tu contacto")
    db.delete(obj); db.commit()
    return {"ok": True}


# ───────────────────── Barrios (Mod #5) ─────────────────────

@router.get("/barrios", response_model=List[sv.BarrioOut])
def listar_barrios(db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_vendedor(db, user)
    return db.query(mv.VentasBarrio).order_by(mv.VentasBarrio.nombre).all()


@router.post("/barrios", response_model=sv.BarrioOut)
def crear_barrio(data: sv.BarrioCreate,
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo el admin gestiona barrios")
    obj = mv.VentasBarrio(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.patch("/barrios/{bid}", response_model=sv.BarrioOut)
def editar_barrio(bid: int, data: sv.BarrioCreate,
                  db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo el admin gestiona barrios")
    obj = db.query(mv.VentasBarrio).filter_by(id=bid).first()
    if not obj:
        raise HTTPException(404, "Barrio no encontrado")
    for k, val in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, val)
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/barrios/{bid}")
def eliminar_barrio(bid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo el admin gestiona barrios")
    obj = db.query(mv.VentasBarrio).filter_by(id=bid).first()
    if not obj:
        raise HTTPException(404, "Barrio no encontrado")
    db.delete(obj); db.commit()
    return {"ok": True}


@router.post("/geocodificar", response_model=sv.GeocodeOut)
def geocodificar(data: sv.GeocodeRequest,
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Mod #5: resuelve dirección → lat/lng + barrio (point-in-polygon)."""
    get_vendedor(db, user)
    return ventas_geo.resolver(db, data.direccion, data.ciudad)


# ───────────────────── Comisión config (Mod #4) ─────────────────────

@router.get("/comision-config", response_model=List[sv.ComisionConfigOut])
def listar_comision_config(vendedor_id: Optional[int] = None,
                           db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    q = db.query(mv.VentasComisionConfig)
    if v.es_admin:
        if vendedor_id:
            q = q.filter(mv.VentasComisionConfig.vendedor_id == vendedor_id)
    else:
        q = q.filter(mv.VentasComisionConfig.vendedor_id == v.id)
    return q.order_by(mv.VentasComisionConfig.id).all()


@router.post("/comision-config", response_model=sv.ComisionConfigOut)
def crear_comision_config(data: sv.ComisionConfigCreate,
                          db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo el admin configura comisiones")
    payload = data.model_dump()
    payload["tipo"] = _enum(mv.VPropiedadTipo, payload.get("tipo"), "tipo")
    # Upsert: si ya existe (vendedor, tipo), actualizar el pct
    existente = (db.query(mv.VentasComisionConfig)
                 .filter_by(vendedor_id=payload["vendedor_id"], tipo=payload["tipo"]).first())
    if existente:
        existente.comision_pct = payload["comision_pct"]
        db.commit(); db.refresh(existente)
        return existente
    obj = mv.VentasComisionConfig(**payload)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.delete("/comision-config/{cid}")
def eliminar_comision_config(cid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo el admin configura comisiones")
    obj = db.query(mv.VentasComisionConfig).filter_by(id=cid).first()
    if not obj:
        raise HTTPException(404, "Config no encontrada")
    db.delete(obj); db.commit()
    return {"ok": True}


# ───────────────────── Valor m² referencia (Mod #1 fallback) ─────────────────────

@router.get("/valor-m2", response_model=List[sv.ValorM2Out])
def listar_valor_m2(db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_vendedor(db, user)
    return db.query(mv.VentasValorM2Referencia).order_by(mv.VentasValorM2Referencia.id).all()


@router.post("/valor-m2", response_model=sv.ValorM2Out)
def crear_valor_m2(data: sv.ValorM2Create,
                   db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo el admin carga valores de referencia")
    payload = data.model_dump()
    payload["tipo"] = _enum(mv.VPropiedadTipo, payload.get("tipo"), "tipo")
    existente = (db.query(mv.VentasValorM2Referencia)
                 .filter_by(barrio_id=payload["barrio_id"], tipo=payload["tipo"]).first())
    if existente:
        existente.valor_m2_usd = payload["valor_m2_usd"]
        db.commit(); db.refresh(existente)
        return existente
    obj = mv.VentasValorM2Referencia(**payload)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.delete("/valor-m2/{vid}")
def eliminar_valor_m2(vid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo el admin carga valores de referencia")
    obj = db.query(mv.VentasValorM2Referencia).filter_by(id=vid).first()
    if not obj:
        raise HTTPException(404, "No encontrado")
    db.delete(obj); db.commit()
    return {"ok": True}


# ───────────────────── Propiedades vinculadas a un pedido ─────────────────────

@router.get("/pedidos/{pid}/propiedades", response_model=List[sv.PedidoPropOut])
def listar_pedido_propiedades(pid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    ped = _scope(db.query(mv.VentasPedido), mv.VentasPedido, v).filter_by(id=pid).first()
    if not ped:
        raise HTTPException(404, "Pedido no encontrado")
    return (db.query(mv.VentasPedidoPropiedad).filter_by(pedido_id=pid)
            .order_by(mv.VentasPedidoPropiedad.id.desc()).all())


@router.post("/pedidos/{pid}/propiedades", response_model=sv.PedidoPropOut)
def vincular_propiedad(pid: int, data: sv.PedidoPropCreate,
                       db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    ped = _scope(db.query(mv.VentasPedido), mv.VentasPedido, v).filter_by(id=pid).first()
    if not ped:
        raise HTTPException(404, "Pedido no encontrado")
    # Validar que la propiedad exista
    if not db.query(mv.VentasPropiedad).filter_by(id=data.propiedad_id).first():
        raise HTTPException(404, "Propiedad no encontrada")
    if data.estado not in _ESTADOS_VINCULO:
        raise HTTPException(400, f"estado inválido: opciones {', '.join(_ESTADOS_VINCULO)}")
    ya = (db.query(mv.VentasPedidoPropiedad)
          .filter_by(pedido_id=pid, propiedad_id=data.propiedad_id).first())
    if ya:
        raise HTTPException(409, "Esa propiedad ya está vinculada a este pedido")
    obj = mv.VentasPedidoPropiedad(pedido_id=pid, **data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


def _vinculo_propio(db, ppid, v):
    """Devuelve el vínculo si el pedido pertenece al vendedor (o es admin)."""
    obj = db.query(mv.VentasPedidoPropiedad).filter_by(id=ppid).first()
    if not obj:
        raise HTTPException(404, "Vínculo no encontrado")
    ped = db.query(mv.VentasPedido).filter_by(id=obj.pedido_id).first()
    if not v.es_admin and (not ped or ped.vendedor_id != v.id):
        raise HTTPException(403, "No es tu pedido")
    return obj


@router.patch("/pedido-propiedad/{ppid}", response_model=sv.PedidoPropOut)
def cambiar_estado_vinculo(ppid: int, estado: str = Query(...),
                           db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    obj = _vinculo_propio(db, ppid, v)
    if estado not in _ESTADOS_VINCULO:
        raise HTTPException(400, f"estado inválido: opciones {', '.join(_ESTADOS_VINCULO)}")
    obj.estado = estado
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/pedido-propiedad/{ppid}")
def desvincular_propiedad(ppid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    obj = _vinculo_propio(db, ppid, v)
    db.delete(obj); db.commit()
    return {"ok": True}


# ───────────────────── Tasaciones (Mod #1) ─────────────────────

@router.post("/tasaciones", response_model=sv.TasacionOut)
def tasar_propiedad(data: sv.TasacionRequest,
                    db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    data.tipo = _enum(mv.VPropiedadTipo, data.tipo, "tipo").value if data.tipo else "casa"
    resultado = tasar(db, data)
    obj = mv.VentasTasacion(**resultado, generado_por=v.id)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.get("/tasaciones", response_model=List[sv.TasacionOut])
def listar_tasaciones(db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    q = db.query(mv.VentasTasacion)
    if not v.es_admin:
        q = q.filter(mv.VentasTasacion.generado_por == v.id)
    return q.order_by(mv.VentasTasacion.id.desc()).all()


# ───────────────────── Dashboard ─────────────────────

@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    pedidos = _scope(db.query(mv.VentasPedido), mv.VentasPedido, v).all()
    clientes = _scope(db.query(mv.VentasCliente), mv.VentasCliente, v).all()
    ops = _scope(db.query(mv.VentasOperacion), mv.VentasOperacion, v).all()
    props_disp = db.query(mv.VentasPropiedad).filter(
        mv.VentasPropiedad.estado == mv.VPropiedadEstado.disponible
    ).count()

    por_estado = {e.value: 0 for e in mv.PedidoEstado}
    for p in pedidos:
        est = p.estado.value if hasattr(p.estado, "value") else p.estado
        por_estado[est] = por_estado.get(est, 0) + 1

    cerradas = [o for o in ops if (o.estado.value if hasattr(o.estado, "value") else o.estado) == "cerrada"]
    comisiones = sum(o.comision_monto_usd or 0 for o in cerradas)

    return {
        "es_admin": v.es_admin,
        "total_clientes": len(clientes),
        "clientes_operados": len([c for c in clientes if c.es_operado]),
        "total_pedidos": len(pedidos),
        "pedidos_por_estado": por_estado,
        "propiedades_disponibles": props_disp,
        "operaciones_cerradas": len(cerradas),
        "monto_cerrado_usd": sum(o.monto_cierre_usd or 0 for o in cerradas),
        "comisiones_usd": round(comisiones, 2),
    }
