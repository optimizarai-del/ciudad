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
import time
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import text, bindparam

from app.database import get_db, IS_POSTGRES
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
    if role not in ("admin", "gerencia", "ventas", "ventas_admin", "admin_demo"):
        raise HTTPException(403, "No tenés acceso al módulo de Ventas")
    # admin/gerencia y el usuario demo ven todo su workspace (es_admin=True).
    es_admin = role in ("admin", "gerencia", "ventas_admin", "admin_demo")
    v = mv.VentasVendedor(
        user_id=user.id,
        nombre=user.nombre,
        es_admin=es_admin,
        is_demo=(role == "admin_demo"),
    )
    db.add(v); db.commit(); db.refresh(v)
    return v


def _audit(db, vendedor, entidad, entidad_id, accion, detalle=None):
    db.add(mv.VentasAuditLog(
        vendedor_id=vendedor.id, entidad=entidad, entidad_id=entidad_id,
        accion=accion, detalle=json.dumps(detalle, ensure_ascii=False, default=str) if detalle else None,
    ))


def _demo(query, model, vendedor):
    """Aísla el sandbox demo: filtra por is_demo == el del vendedor. El usuario
    demo (is_demo=True) ve solo data demo; los reales solo ven la real. Se aplica
    a TODO modelo de Ventas que tenga la columna is_demo (entidades compartidas
    como propiedades y matches, además de las scopeadas por vendedor)."""
    if hasattr(model, "is_demo"):
        return query.filter(model.is_demo == bool(vendedor.is_demo))
    return query


def _scope(query, model, vendedor):
    """Filtra por sandbox demo y por vendedor (salvo admin, que ve todo su
    workspace)."""
    query = _demo(query, model, vendedor)
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
    from datetime import datetime
    v = get_vendedor(db, user)
    # exclude_none para no pisar los defaults del modelo (etapa/temperatura).
    obj = mv.VentasCliente(**data.model_dump(exclude_none=True), vendedor_id=v.id)
    obj.is_demo = bool(v.is_demo)
    obj.etapa_desde = datetime.utcnow()
    db.add(obj); db.flush()
    _log_evento(db, v, obj.id, "etapa", None, obj.etapa, "Lead creado")
    _audit(db, v, "ventas_clientes", obj.id, mv.AuditAccion.create, data.model_dump())
    db.commit(); db.refresh(obj)
    return obj


@router.patch("/clientes/{cid}", response_model=sv.ClienteOut)
def editar_cliente(cid: int, data: sv.ClienteUpdate,
                   db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    obj = _scope(db.query(mv.VentasCliente), mv.VentasCliente, v).filter_by(id=cid).first()
    if not obj:
        raise HTTPException(404, "Cliente no encontrado")
    cambios = data.model_dump(exclude_unset=True)
    temp_anterior = obj.temperatura
    for k, val in cambios.items():
        setattr(obj, k, val)
    if "temperatura" in cambios and cambios["temperatura"] != temp_anterior:
        _log_evento(db, v, obj.id, "temperatura", temp_anterior, obj.temperatura, "Cambio manual")
    _audit(db, v, "ventas_clientes", obj.id, mv.AuditAccion.update, cambios)
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


def _log_evento(db, v, cliente_id, tipo, de, a, detalle=None, automatico=False):
    """Registra un evento del pipeline (timeline + métricas)."""
    db.add(mv.VentasClienteEvento(
        cliente_id=cliente_id, vendedor_id=(v.id if v else None),
        tipo=tipo, de=de, a=a, detalle=detalle, automatico=automatico))


# Etapas que exigen el perfil base completo (doc §3.5: transición 2→3).
_ETAPAS_REQUIEREN_PERFIL = {
    "calificado_activo", "presentacion_opciones", "en_visitas",
    "oferta_negociacion", "reserva_sena", "escritura_cierre",
}
_ETAPAS_PAUSA = {"caido_perdido", "frio_espera"}
_ETAPAS_VALIDAS = {e.value for e in mv.ClienteEtapa}


def _validar_avance(cli, nueva_etapa: str, motivo: str | None):
    """Criterios de avance (doc §3.5). Devuelve None si OK, o un mensaje de error."""
    if nueva_etapa not in _ETAPAS_VALIDAS:
        return f"Etapa inválida: {nueva_etapa}"
    # Hard rule: pausa requiere motivo
    if nueva_etapa in _ETAPAS_PAUSA and not (motivo and motivo.strip()):
        return "Para mandar el lead a Perdido o Frío/En espera es obligatorio registrar un motivo."
    # Hard rule: perfil base para entrar a Calificado-Activo y posteriores
    if nueva_etapa in _ETAPAS_REQUIEREN_PERFIL:
        faltan = []
        if not cli.perfil_comprador: faltan.append("perfil de comprador")
        if not (cli.presupuesto_min_usd or cli.presupuesto_max_usd): faltan.append("presupuesto")
        if not cli.zona_interes: faltan.append("zona de interés")
        if faltan:
            return ("Para avanzar a esta etapa completá el perfil base: " + ", ".join(faltan) + ".")
    return None


@router.post("/clientes/{cid}/interaccion")
def registrar_interaccion(cid: int, data: sv.InteraccionCreate,
                          db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Cambio 1.2 — Registra una interacción: nota + PRÓXIMA ACCIÓN OBLIGATORIA.
    No se puede cerrar el log sin definir la próxima acción (regla del doc)."""
    from datetime import datetime
    v = get_vendedor(db, user)
    cli = _scope(db.query(mv.VentasCliente), mv.VentasCliente, v).filter_by(id=cid).first()
    if not cli:
        raise HTTPException(404, "Cliente no encontrado")
    if not (data.proxima_accion_contexto and data.proxima_accion_contexto.strip()):
        raise HTTPException(400, "La próxima acción es obligatoria: definí tipo, fecha y contexto.")
    # Nota = interacción
    nota = mv.VentasClienteNota(cliente_id=cid, vendedor_id=v.id,
                                texto=data.texto, origen=data.origen)
    db.add(nota)
    # Actualizar próxima acción + último contacto
    cli.proxima_accion_tipo = data.proxima_accion_tipo
    cli.proxima_accion_fecha = data.proxima_accion_fecha
    cli.proxima_accion_contexto = data.proxima_accion_contexto
    cli.ultimo_contacto_at = datetime.utcnow()
    if data.temperatura and data.temperatura != cli.temperatura:
        _log_evento(db, v, cid, "temperatura", cli.temperatura, data.temperatura, "Actualizada en interacción")
        cli.temperatura = data.temperatura
    # Reset del aviso previo de enfriamiento (hubo actividad)
    cli.temp_alerta_previa_at = None
    _log_evento(db, v, cid, "interaccion", None, data.proxima_accion_tipo,
                f"{data.texto[:120]} · próx: {data.proxima_accion_contexto[:80]}")
    db.commit()
    return {"ok": True, "ultimo_contacto_at": cli.ultimo_contacto_at.isoformat()}


@router.patch("/clientes/{cid}/etapa", response_model=sv.ClienteOut)
def cambiar_etapa(cid: int, data: sv.ClienteEtapaUpdate,
                  db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Cambio 1.3 — Avanza/retrocede la etapa del cliente con criterios de avance
    (doc §3.5) y motivo obligatorio para pausas."""
    from datetime import datetime
    v = get_vendedor(db, user)
    cli = _scope(db.query(mv.VentasCliente), mv.VentasCliente, v).filter_by(id=cid).first()
    if not cli:
        raise HTTPException(404, "Cliente no encontrado")
    err = _validar_avance(cli, data.etapa, data.motivo)
    if err:
        raise HTTPException(400, err)
    anterior = cli.etapa
    if data.etapa == anterior:
        return cli
    cli.etapa = data.etapa
    cli.etapa_desde = datetime.utcnow()
    if data.etapa in _ETAPAS_PAUSA:
        cli.motivo_pausa = data.motivo
    if data.etapa == "escritura_cierre":
        cli.es_operado = True
    _log_evento(db, v, cid, "etapa", anterior, data.etapa, data.motivo)
    _audit(db, v, "ventas_clientes", cid, mv.AuditAccion.update, {"etapa": data.etapa})
    db.commit(); db.refresh(cli)
    return cli


@router.get("/clientes/{cid}/eventos", response_model=List[sv.ClienteEventoOut])
def listar_eventos_cliente(cid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    cli = _scope(db.query(mv.VentasCliente), mv.VentasCliente, v).filter_by(id=cid).first()
    if not cli:
        raise HTTPException(404, "Cliente no encontrado")
    return (db.query(mv.VentasClienteEvento).filter_by(cliente_id=cid)
            .order_by(mv.VentasClienteEvento.created_at.desc()).limit(100).all())


@router.get("/pipeline")
def pipeline_clientes(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Cambio 1.3 — Clientes agrupados por etapa del pipeline (para kanban) +
    flags de urgencia para el panel de temperatura."""
    from datetime import datetime
    from app.services import ventas_pipeline as vp
    v = get_vendedor(db, user)
    clientes = _scope(db.query(mv.VentasCliente), mv.VentasCliente, v).all()
    ahora = datetime.utcnow()
    orden_temp = {"caliente": 0, "tibio": 1, "frio": 2}
    sla_map = vp.get_sla_map(db)
    en_consulta = {q.cliente_id for q in db.query(mv.VentasLiderConsulta.cliente_id)
                   .filter(mv.VentasLiderConsulta.estado == "pendiente")}
    out = []
    for c in clientes:
        prox = c.proxima_accion_fecha
        vencida = bool(prox and prox < ahora)
        dias_sin_contacto = ((ahora - c.ultimo_contacto_at).days
                             if c.ultimo_contacto_at else None)
        dias_en_etapa = ((ahora - c.etapa_desde).days if c.etapa_desde else None)
        sla = vp.sla_estado(c, sla_map, ahora)
        out.append({
            "id": c.id, "nombre": c.nombre, "telefono": c.telefono,
            "etapa": c.etapa or "nuevo_lead",
            "temperatura": c.temperatura or "tibio",
            "perfil_comprador": c.perfil_comprador,
            "tipo_operacion": c.tipo_operacion,
            "presupuesto_min_usd": c.presupuesto_min_usd,
            "presupuesto_max_usd": c.presupuesto_max_usd,
            "zona_interes": c.zona_interes,
            "proxima_accion_tipo": c.proxima_accion_tipo,
            "proxima_accion_fecha": c.proxima_accion_fecha.isoformat() if c.proxima_accion_fecha else None,
            "proxima_accion_contexto": c.proxima_accion_contexto,
            "sin_proxima_accion": not c.proxima_accion_fecha,
            "proxima_accion_vencida": vencida,
            "dias_sin_contacto": dias_sin_contacto,
            "dias_en_etapa": dias_en_etapa,
            "sla_vencido": sla["sla_vencido"],
            "en_consulta_lider": c.id in en_consulta,
            "vendedor_id": c.vendedor_id,
        })
    # Orden para el panel de temperatura: temp, luego acción vencida, luego sin acción
    out.sort(key=lambda x: (
        orden_temp.get(x["temperatura"], 1),
        0 if x["proxima_accion_vencida"] else 1,
        0 if x["sin_proxima_accion"] else 1,
        x["proxima_accion_fecha"] or "9999",
    ))
    return {"total": len(out), "clientes": out,
            "etapas": [e.value for e in mv.CLIENTE_ETAPAS_ORDEN] + [e.value for e in mv.CLIENTE_ETAPAS_PAUSA]}


# ── Fase 2: job, consultas al líder y SLA ──

@router.post("/pipeline/jobs/run")
def pipeline_run_jobs(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Corre degradación + resolución de consultas vencidas (Fase 2). Pensado
    para el cron diario; también se puede disparar a mano (admin)."""
    from app.services import ventas_pipeline as vp
    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo un admin puede correr el job del pipeline.")
    return vp.run_pipeline_jobs(db)


@router.get("/pipeline/consultas")
def pipeline_consultas(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Consultas de degradación pendientes para el líder (doc §7.1)."""
    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo el líder/admin ve las consultas de degradación.")
    qs = (db.query(mv.VentasLiderConsulta)
          .filter_by(estado="pendiente")
          .order_by(mv.VentasLiderConsulta.creada_at.asc()).all())
    out = []
    for q in qs:
        c = db.get(mv.VentasCliente, q.cliente_id)
        out.append({
            "id": q.id, "cliente_id": q.cliente_id,
            "cliente_nombre": c.nombre if c else "—",
            "vendedor_id": q.vendedor_id,
            "de_temp": q.de_temp, "a_temp": q.a_temp,
            "creada_at": q.creada_at.isoformat() if q.creada_at else None,
            "vence_at": q.vence_at.isoformat() if q.vence_at else None,
        })
    return {"consultas": out}


@router.post("/pipeline/consultas/{qid}/resolver")
def pipeline_resolver_consulta(qid: int, payload: dict,
                               db: Session = Depends(get_db), user=Depends(get_current_user)):
    """El líder resuelve: confirmar | posponer | reasignar (con vendedor destino)."""
    from app.services import ventas_pipeline as vp
    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo el líder/admin resuelve consultas.")
    try:
        return vp.resolver_consulta(
            db, qid, accion=payload.get("accion"),
            detalle=payload.get("detalle", ""),
            reasignar_a=payload.get("reasignar_a"))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/pipeline/sla")
def pipeline_get_sla(db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.services import ventas_pipeline as vp
    get_vendedor(db, user)
    return {"sla": vp.get_sla_map(db)}


@router.put("/pipeline/sla")
def pipeline_set_sla(payload: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Actualiza SLA por etapa (admin). payload: {etapa: horas|null, ...}."""
    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo un admin configura los SLA.")
    from app.services import ventas_pipeline as vp
    vp.seed_sla(db)
    for etapa, horas in (payload or {}).items():
        fila = db.query(mv.VentasPipelineSLA).filter_by(etapa=etapa).first()
        if fila:
            fila.horas_sla = horas
        else:
            db.add(mv.VentasPipelineSLA(etapa=etapa, horas_sla=horas))
    db.commit()
    return {"ok": True, "sla": vp.get_sla_map(db)}


# ── Fase 3: métricas del pipeline, vista líder y export ──

@router.get("/pipeline/metricas")
def pipeline_metricas(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """KPIs del pipeline (embudo, conversión, temperatura, riesgo, valor) sobre
    los clientes visibles para el usuario (admin ve todo)."""
    from app.services import ventas_pipeline as vp
    v = get_vendedor(db, user)
    clientes = _scope(db.query(mv.VentasCliente), mv.VentasCliente, v).all()
    m = vp.metricas(db, clientes)
    m["es_admin"] = v.es_admin
    return m


@router.get("/pipeline/lider")
def pipeline_lider(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Performance por vendedor (solo líder/admin)."""
    from app.services import ventas_pipeline as vp
    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo el líder/admin ve la performance del equipo.")
    return vp.metricas_lider(db, es_demo=bool(v.is_demo))


@router.get("/dashboard-ejecutivo")
def dashboard_ejecutivo(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Foto ejecutiva del negocio (solo líder/admin): cruza el pipeline de
    clientes, la captación por canal, las operaciones y el inventario.

    Pensado para el dueño/gerencia: una sola pantalla con los números que
    importan, sin tener que recorrer cada módulo."""
    from datetime import datetime, timedelta
    from app.services import ventas_pipeline as vp

    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo el líder/admin ve el dashboard ejecutivo.")

    ahora = datetime.utcnow()
    hace_30 = ahora - timedelta(days=30)

    clientes = _demo(db.query(mv.VentasCliente), mv.VentasCliente, v).all()
    pipeline = vp.metricas(db, clientes, ahora)

    # ── Captación por canal (origen) ──
    canales: dict[str, dict] = {}
    for c in clientes:
        canal = (c.origen or "sin_origen").strip().lower()
        d = canales.setdefault(canal, {"canal": canal, "total": 0, "ult_30d": 0})
        d["total"] += 1
        if c.created_at and c.created_at >= hace_30:
            d["ult_30d"] += 1
    captacion = sorted(canales.values(), key=lambda x: x["total"], reverse=True)
    leads_30d = sum(c["ult_30d"] for c in captacion)

    # ── Operaciones ──
    ops = _demo(db.query(mv.VentasOperacion), mv.VentasOperacion, v).all()
    est_ops = {e.value: 0 for e in mv.OperacionEstado}
    comision_cerrada = 0.0
    monto_cerrado = 0.0
    for o in ops:
        est = o.estado.value if hasattr(o.estado, "value") else (o.estado or "abierta")
        est_ops[est] = est_ops.get(est, 0) + 1
        if est == "cerrada":
            comision_cerrada += float(o.comision_monto_usd or 0)
            monto_cerrado += float(o.monto_cierre_usd or 0)
    operaciones = {
        "por_estado": [{"estado": k, "n": v} for k, v in est_ops.items()],
        "abiertas": est_ops.get("abierta", 0) + est_ops.get("sena", 0),
        "cerradas": est_ops.get("cerrada", 0),
        "monto_cerrado_usd": round(monto_cerrado, 0),
        "comision_cerrada_usd": round(comision_cerrada, 0),
    }

    # ── Inventario de propiedades ──
    props = _demo(db.query(mv.VentasPropiedad), mv.VentasPropiedad, v).all()
    por_estado = {e.value: 0 for e in mv.VPropiedadEstado}
    por_fuente = {e.value: 0 for e in mv.VPropiedadFuente}
    valor_inventario = 0.0
    for p in props:
        est = p.estado.value if hasattr(p.estado, "value") else (p.estado or "disponible")
        fte = p.fuente.value if hasattr(p.fuente, "value") else (p.fuente or "propia")
        por_estado[est] = por_estado.get(est, 0) + 1
        por_fuente[fte] = por_fuente.get(fte, 0) + 1
        if est == "disponible" and p.precio_usd:
            valor_inventario += float(p.precio_usd)
    inventario = {
        "total": len(props),
        "por_estado": [{"estado": k, "n": v} for k, v in por_estado.items()],
        "por_fuente": [{"fuente": k, "n": v} for k, v in por_fuente.items()],
        "valor_disponible_usd": round(valor_inventario, 0),
    }

    return {
        "generado_at": ahora.isoformat(),
        "resumen": {
            "clientes_total": len(clientes),
            "leads_ult_30d": leads_30d,
            "pipeline_valor_usd": pipeline["valor_pipeline_usd"],
            "pipeline_ponderado_usd": pipeline["valor_ponderado_usd"],
            "operaciones_abiertas": operaciones["abiertas"],
            "operaciones_cerradas": operaciones["cerradas"],
            "comision_cerrada_usd": operaciones["comision_cerrada_usd"],
            "inventario_disponible": next(
                (x["n"] for x in inventario["por_estado"] if x["estado"] == "disponible"), 0),
        },
        "pipeline": pipeline,
        "captacion": captacion,
        "operaciones": operaciones,
        "inventario": inventario,
        "equipo": vp.metricas_lider(db, ahora, es_demo=bool(v.is_demo)),
    }


_EXPORT_COLS = [
    ("id", "ID"), ("nombre", "Cliente"), ("telefono", "Teléfono"),
    ("etapa", "Etapa"), ("temperatura", "Temperatura"),
    ("perfil_comprador", "Perfil"), ("tipo_operacion", "Operación"),
    ("presupuesto_min_usd", "Presup. mín USD"), ("presupuesto_max_usd", "Presup. máx USD"),
    ("zona_interes", "Zona"), ("proxima_accion_tipo", "Próx. acción"),
    ("proxima_accion_fecha", "Próx. fecha"), ("ultimo_contacto_at", "Últ. contacto"),
    ("dias_en_etapa", "Días en etapa"), ("vendedor", "Vendedor"),
]


def _export_filas(db, clientes, ahora):
    from app.services import ventas_pipeline as vp
    vends = {v.id: v.nombre for v in db.query(mv.VentasVendedor).all()}
    filas = []
    for c in clientes:
        dias_etapa = ((ahora - c.etapa_desde).days if c.etapa_desde else None)
        filas.append({
            "id": c.id, "nombre": c.nombre, "telefono": c.telefono or "",
            "etapa": vp.ETIQUETA_ETAPA.get(c.etapa or "nuevo_lead", c.etapa or ""),
            "temperatura": c.temperatura or "tibio",
            "perfil_comprador": c.perfil_comprador or "",
            "tipo_operacion": c.tipo_operacion or "",
            "presupuesto_min_usd": c.presupuesto_min_usd or "",
            "presupuesto_max_usd": c.presupuesto_max_usd or "",
            "zona_interes": c.zona_interes or "",
            "proxima_accion_tipo": c.proxima_accion_tipo or "",
            "proxima_accion_fecha": c.proxima_accion_fecha.strftime("%Y-%m-%d") if c.proxima_accion_fecha else "",
            "ultimo_contacto_at": c.ultimo_contacto_at.strftime("%Y-%m-%d") if c.ultimo_contacto_at else "",
            "dias_en_etapa": dias_etapa if dias_etapa is not None else "",
            "vendedor": vends.get(c.vendedor_id, ""),
        })
    return filas


@router.get("/pipeline/export.csv")
def pipeline_export_csv(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Export del pipeline en CSV (UTF-8-BOM, abre nativo en Excel)."""
    import csv, io
    from datetime import datetime
    from fastapi.responses import StreamingResponse
    v = get_vendedor(db, user)
    clientes = _scope(db.query(mv.VentasCliente), mv.VentasCliente, v).all()
    filas = _export_filas(db, clientes, datetime.utcnow())
    buf = io.StringIO()
    buf.write("﻿")  # BOM para Excel
    w = csv.writer(buf, delimiter=";")
    w.writerow([label for _, label in _EXPORT_COLS])
    for f in filas:
        w.writerow([f[key] for key, _ in _EXPORT_COLS])
    buf.seek(0)
    fname = f"pipeline_{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.get("/pipeline/export.pdf")
def pipeline_export_pdf(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Resumen ejecutivo del pipeline en PDF (embudo + KPIs + tabla de clientes)."""
    import io
    from datetime import datetime
    from fastapi.responses import StreamingResponse
    from app.services import ventas_pipeline as vp
    v = get_vendedor(db, user)
    clientes = _scope(db.query(mv.VentasCliente), mv.VentasCliente, v).all()
    ahora = datetime.utcnow()
    m = vp.metricas(db, clientes, ahora)
    filas = _export_filas(db, clientes, ahora)
    pdf = _pipeline_pdf(m, filas, es_admin=v.es_admin)
    fname = f"pipeline_{date.today().isoformat()}.pdf"
    return StreamingResponse(
        iter([pdf]), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'})


def _pipeline_pdf(m: dict, filas: list, es_admin: bool) -> bytes:
    """Genera el PDF del pipeline con reportlab. Identidad CIUDAD (dorado)."""
    import io
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle)

    ORO = colors.HexColor("#B8893A")
    GRIS = colors.HexColor("#737373")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm,
                            leftMargin=16 * mm, rightMargin=16 * mm, title="Pipeline CIUDAD")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=20, textColor=colors.black, spaceAfter=2)
    eyebrow = ParagraphStyle("eb", parent=ss["Normal"], fontSize=8, textColor=ORO,
                             spaceAfter=8, leading=10)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=11, textColor=colors.black,
                        spaceBefore=10, spaceAfter=6)
    small = ParagraphStyle("sm", parent=ss["Normal"], fontSize=8, textColor=GRIS)

    def fusd(n):
        return f"USD {int(n or 0):,}".replace(",", ".")

    el = []
    el.append(Paragraph("CRM COMERCIAL · CIUDAD", eyebrow))
    el.append(Paragraph("Resumen del Pipeline", h1))
    el.append(Paragraph(date.today().strftime("Generado el %d/%m/%Y") +
                        (" · vista equipo" if es_admin else " · tu cartera"), small))
    el.append(Spacer(1, 8 * mm))

    # KPIs
    kpis = [
        ["Clientes activos", str(m["activos"])],
        ["Valor del pipeline", fusd(m["valor_pipeline_usd"])],
        ["Valor ponderado", fusd(m["valor_ponderado_usd"])],
        ["Sin próxima acción", str(m["riesgo"]["sin_proxima_accion"])],
        ["Acción vencida", str(m["riesgo"]["proxima_accion_vencida"])],
        ["SLA vencido", str(m["riesgo"]["sla_vencido"])],
    ]
    kt = Table([[Paragraph(f"<font size=8 color='#737373'>{k}</font><br/>"
                           f"<font size=15>{val}</font>", ss["Normal"])
                 for k, val in kpis[i:i + 3]] for i in (0, 3)],
               colWidths=[58 * mm] * 3)
    kt.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E5E5")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E5E5")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    el.append(kt)

    # Embudo
    el.append(Paragraph("Embudo por etapa", h2))
    maxn = max([e["alcanzaron"] for e in m["embudo"]] + [1])
    emb_rows = []
    for e in m["embudo"]:
        barra = "█" * max(1, round(24 * e["alcanzaron"] / maxn)) if e["alcanzaron"] else ""
        emb_rows.append([e["label"], str(e["alcanzaron"]),
                         Paragraph(f"<font color='#B8893A'>{barra}</font>", ss["Normal"])])
    et = Table([["Etapa", "Alcanzaron", ""]] + emb_rows,
               colWidths=[55 * mm, 25 * mm, 98 * mm])
    et.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), GRIS),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#E5E5E5")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    el.append(et)

    # Tabla de clientes (primeros 40)
    el.append(Paragraph("Clientes del pipeline", h2))
    head = ["Cliente", "Etapa", "Temp.", "Próx. acción", "Días"]
    body = [[f["nombre"][:26], f["etapa"], f["temperatura"],
             (f["proxima_accion_fecha"] or "—"), str(f["dias_en_etapa"] or "—")]
            for f in filas[:40]]
    ct = Table([head] + body, colWidths=[46 * mm, 44 * mm, 20 * mm, 30 * mm, 18 * mm])
    ct.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (-1, 0), GRIS),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#E5E5E5")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    el.append(ct)
    if len(filas) > 40:
        el.append(Spacer(1, 3 * mm))
        el.append(Paragraph(f"… y {len(filas) - 40} clientes más (ver CSV).", small))

    doc.build(el)
    return buf.getvalue()


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
    def _estado(p):
        return p.estado.value if hasattr(p.estado, "value") else p.estado
    activos = [p for p in pedidos if _estado(p) not in ("cerrado", "perdido")]

    # Rango de presupuesto buscado (de los pedidos activos)
    maxs = [p.precio_max_usd for p in activos if p.precio_max_usd]
    presupuesto = _fmt_usd(max(maxs)) if maxs else None

    # Acciones recomendadas — agente IA personalizado por cliente.
    # Usa Claude si hay ANTHROPIC_API_KEY; si no, cae a reglas determinísticas.
    from app.services.ventas_recomendaciones import recomendar_acciones
    _ctx = {
        "nombre": cli.nombre,
        "es_operado": cli.es_operado,
        "dias_sin_contacto": dias_sin_contacto,
        "presupuesto_max": presupuesto,
        "operaciones": len(ops),
        "pedidos": [{
            "tipo": (p.tipo.value if p.tipo and hasattr(p.tipo, "value") else p.tipo),
            "zona": p.zona,
            "estado": _estado(p),
            "precio_max": p.precio_max_usd,
        } for p in pedidos],
        "notas": [{
            "texto": n.texto,
            "fecha": n.created_at.strftime("%d/%m/%Y") if n.created_at else None,
        } for n in sorted(notas, key=lambda x: x.created_at or datetime.min, reverse=True)],
    }
    _rec = recomendar_acciones(_ctx)
    recs = _rec["recomendaciones"]
    motor_recs = _rec["motor"]

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
        "recomendaciones_motor": motor_recs,
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
    v = get_vendedor(db, user)  # garantiza acceso
    query = _demo(db.query(mv.VentasPropiedad), mv.VentasPropiedad, v)
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
    obj = mv.VentasPropiedad(**payload, cargada_por=v.id, is_demo=bool(v.is_demo))
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


# ───────────────────── Mapa interactivo (Mod #5 — geo) ─────────────────────

# Centro por defecto de las ciudades de cobertura (Santa Rosa / Toay, La Pampa).
_CENTRO_DEFAULT = {"lat": -36.6203, "lng": -64.2906, "zoom": 13}


@router.get("/propiedades/mapa")
def propiedades_mapa(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Datos livianos para el mapa: propiedades georreferenciadas + polígonos de
    barrio. Incluye el conteo de propiedades sin coordenadas (pendientes de
    geocodificar) para mostrar el aviso de backfill en el front."""
    get_vendedor(db, user)
    props = db.query(mv.VentasPropiedad).all()
    con_geo, sin_geo = [], 0
    for p in props:
        if p.lat is not None and p.lng is not None:
            con_geo.append({
                "id": p.id,
                "titulo": p.titulo,
                "tipo": p.tipo.value if p.tipo else None,
                "estado": p.estado.value if p.estado else None,
                "fuente": p.fuente.value if p.fuente else None,
                "direccion": p.direccion,
                "ciudad": p.ciudad,
                "barrio_id": p.barrio_id,
                "lat": p.lat,
                "lng": p.lng,
                "precio_usd": p.precio_usd,
                "superficie_m2": p.superficie_m2,
                "dormitorios": p.dormitorios,
                "banos": p.banos,
                "link_externo": p.link_externo,
            })
        elif p.direccion:
            sin_geo += 1

    barrios = []
    for b in db.query(mv.VentasBarrio).all():
        geo = None
        if b.poligono_geojson:
            try:
                geo = json.loads(b.poligono_geojson)
            except Exception:
                geo = None
        barrios.append({
            "id": b.id, "nombre": b.nombre, "ciudad": b.ciudad,
            "color": b.color or "#B8893A", "poligono": geo,
        })

    # Centrar en el promedio de las propiedades si las hay; si no, default.
    if con_geo:
        centro = {
            "lat": sum(p["lat"] for p in con_geo) / len(con_geo),
            "lng": sum(p["lng"] for p in con_geo) / len(con_geo),
            "zoom": 13,
        }
    else:
        centro = dict(_CENTRO_DEFAULT)

    return {
        "centro": centro,
        "propiedades": con_geo,
        "barrios": barrios,
        "sin_geo": sin_geo,
        "total": len(props),
    }


@router.patch("/propiedades/{pid}/ubicacion", response_model=sv.PropiedadOut)
def reubicar_propiedad(pid: int, lat: float = Query(...), lng: float = Query(...),
                       db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Mueve el pin de una propiedad (drag & drop en el mapa). Guarda las nuevas
    coordenadas y reasigna automáticamente el barrio según el polígono que
    contiene el punto."""
    v = get_vendedor(db, user)
    obj = db.query(mv.VentasPropiedad).filter_by(id=pid).first()
    if not obj:
        raise HTTPException(404, "Propiedad no encontrada")
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        raise HTTPException(422, "Coordenadas fuera de rango")
    obj.lat, obj.lng = lat, lng
    barrio = ventas_geo.barrio_de_punto(db, lat, lng)
    obj.barrio_id = barrio.id if barrio else None
    _audit(db, v, "ventas_propiedades", pid, mv.AuditAccion.update,
           {"lat": lat, "lng": lng, "barrio_id": obj.barrio_id})
    db.commit(); db.refresh(obj)
    return obj


@router.post("/propiedades/geocodificar-faltantes")
def geocodificar_faltantes(limite: int = Query(15, le=50),
                           db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Backfill: geocodifica propiedades que tienen dirección pero no coordenadas
    (típico de las importadas de Tokko). Nominatim pide ~1 req/seg, así que se
    procesa un lote acotado por llamada. Devuelve cuántas resolvió."""
    v = get_vendedor(db, user)
    pendientes = (db.query(mv.VentasPropiedad)
                  .filter(mv.VentasPropiedad.lat.is_(None),
                          mv.VentasPropiedad.direccion.isnot(None))
                  .limit(limite).all())
    resueltas, fallidas = 0, 0
    for i, p in enumerate(pendientes):
        if i > 0:
            time.sleep(1)  # rate-limit Nominatim
        try:
            geo = ventas_geo.resolver(db, p.direccion, p.ciudad)
            if geo["lat"] is not None:
                p.lat, p.lng = geo["lat"], geo["lng"]
                if geo["barrio_id"]:
                    p.barrio_id = geo["barrio_id"]
                resueltas += 1
            else:
                fallidas += 1
        except Exception as e:
            print(f"[ventas_crm] geocodificar-faltantes fallback: {e}")
            fallidas += 1
    db.commit()
    restantes = (db.query(mv.VentasPropiedad)
                 .filter(mv.VentasPropiedad.lat.is_(None),
                         mv.VentasPropiedad.direccion.isnot(None)).count())
    return {"resueltas": resueltas, "fallidas": fallidas, "restantes": restantes}


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
    obj = mv.VentasPedido(**payload, vendedor_id=v.id, is_demo=bool(v.is_demo))
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
    obj = mv.VentasOperacion(**payload, vendedor_id=v.id, comision_manual=manual,
                             is_demo=bool(v.is_demo))

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


# ════════════════════════════════════════════════════════════════════════════
#  RED TOKKO — navegar la red (Supabase) e importar al catálogo por petición
#  Lee public.red_tokko_propiedades (poblada por la CLI tokko) y permite
#  importar propiedades seleccionadas a ventas_propiedades (fuente=tokko).
# ════════════════════════════════════════════════════════════════════════════
_TOKKO_TIPO_MAP = {
    "casa": "casa", "departamento": "departamento", "depto": "departamento",
    "ph": "departamento", "terreno": "lote", "lote": "lote", "local": "local",
    "oficina": "oficina", "galpón": "galpon", "galpon": "galpon",
    "campo": "campo", "cochera": "otro",
}


def _map_tokko_tipo(t: str) -> str:
    return _TOKKO_TIPO_MAP.get((t or "").strip().lower(), "otro")


def _post_import_propiedades(db: Session, props: list, max_geocode: int = 25) -> int:
    """Tras importar propiedades externas: asegura geo (para que aparezcan en el
    MAPA) y dispara el matching contra los pedidos activos (para que aparezcan en
    MATCHES). Devuelve la cantidad de matches nuevos generados.

    - Si la propiedad trae lat/lng → solo resuelve el barrio del punto.
    - Si NO trae coords → geocodifica por dirección (cap para no abusar de
      Nominatim) y asigna barrio.
    """
    if not props:
        return 0
    db.flush()  # asignar ids antes de matchear
    geocodificadas = 0
    for obj in props:
        try:
            if obj.lat is not None and obj.lng is not None:
                if obj.barrio_id is None:
                    b = ventas_geo.barrio_de_punto(db, obj.lat, obj.lng)
                    obj.barrio_id = b.id if b else None
            elif obj.direccion and geocodificadas < max_geocode:
                geo = ventas_geo.resolver(db, obj.direccion, obj.ciudad)
                obj.lat, obj.lng = geo["lat"], geo["lng"]
                obj.barrio_id = geo["barrio_id"]
                if geo["lat"] is not None:
                    geocodificadas += 1
        except Exception as e:
            print(f"[ventas_crm] geo post-import fallback: {e}")
    db.flush()
    matches = 0
    for obj in props:
        try:
            matches += ventas_matching.evaluar_propiedad(db, obj)
        except Exception as e:
            print(f"[ventas_crm] matching post-import fallback: {e}")
    return matches


# ════════════════════════════════════════════════════════════════════════════
#  Carga de propiedad desde PDF / imagen / plano con IA (Fase 4.4)
#  Subís la ficha o el plano y Claude extrae los datos → alta en el catálogo.
# ════════════════════════════════════════════════════════════════════════════

@router.post("/propiedades/importar-archivo/preview")
async def propiedad_importar_preview(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Extrae los datos de la propiedad desde el archivo (sin guardar). El
    operador revisa el resultado antes de confirmar. Admite PDF/imagen/DOCX/TXT."""
    from app.services import ventas_prop_import as vpi
    get_vendedor(db, user)
    content = await archivo.read()
    if not content:
        raise HTTPException(400, "El archivo está vacío.")
    if len(content) > 12 * 1024 * 1024:
        raise HTTPException(413, "El archivo supera los 12 MB.")
    try:
        datos = vpi.parsear_propiedad_archivo(content, archivo.filename or "")
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, f"No se pudo procesar el archivo: {e}")
    return {"datos": datos, "archivo": archivo.filename}


@router.post("/propiedades/importar-archivo/confirmar", response_model=sv.PropiedadOut)
def propiedad_importar_confirmar(payload: dict,
                                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Crea la VentasPropiedad a partir del JSON revisado + geo + matching
    (aparece en el mapa y en Matches)."""
    v = get_vendedor(db, user)
    d = payload or {}
    if not (d.get("titulo") or d.get("direccion")):
        raise HTTPException(400, "Falta al menos un título o una dirección.")
    tipo = _enum(mv.VPropiedadTipo, d.get("tipo") or "otro", "tipo")
    obj = mv.VentasPropiedad(
        cargada_por=v.id,
        is_demo=bool(v.is_demo),
        titulo=(d.get("titulo") or d.get("direccion") or "Propiedad")[:200],
        tipo=tipo,
        estado=mv.VPropiedadEstado.disponible,
        fuente=mv.VPropiedadFuente.propia,
        direccion=d.get("direccion"),
        ciudad=" ".join(x for x in [d.get("ciudad"), d.get("provincia")] if x) or None,
        precio_usd=d.get("precio_usd"),
        superficie_m2=d.get("superficie_m2"),
        dormitorios=d.get("dormitorios"),
        banos=d.get("banos"),
        antiguedad_anios=d.get("antiguedad_anios"),
        descripcion=d.get("descripcion"),
        inmobiliaria=d.get("inmobiliaria"),
    )
    db.add(obj)
    # Geo (con constraint por ciudad/provincia) + barrio + matching.
    matches = _post_import_propiedades(db, [obj])
    _audit(db, v, "ventas_propiedades", obj.id, mv.AuditAccion.create, {"via": "pdf_ia"})
    db.commit(); db.refresh(obj)
    return obj


_RED_COLS = ("referencia, direccion, ubicacion, tipo, operacion, precio_num, moneda, "
             "precio_display, m2_cubierta_num, m2_total_num, ambientes_num, "
             "dormitorios_num, banos_num, lat, lng, detalles, publicado_por, "
             "ficha_url, foto")


@router.get("/red-tokko")
def red_tokko_listar(
    zona: Optional[str] = Query(None),
    operacion: Optional[str] = Query(None),
    precio_min: Optional[int] = Query(None),
    precio_max: Optional[int] = Query(None),
    dorm_min: Optional[int] = Query(None),
    limit: int = Query(40),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    """Lista propiedades de la red Tokko guardadas en la base (con filtros)."""
    get_vendedor(db, user)  # auth/scope
    where, params = ["1=1"], {}
    # `ilike` es Postgres; en SQLite usamos `like` (case-insensitive por default).
    like_op = "ilike" if IS_POSTGRES else "like"
    if operacion:  where.append("operacion = :op");                 params["op"] = operacion
    if zona:       where.append(f"ubicacion {like_op} :z");         params["z"] = f"%{zona}%"
    if precio_min: where.append("precio_num >= :pmin");             params["pmin"] = precio_min
    if precio_max: where.append("precio_num <= :pmax");             params["pmax"] = precio_max
    if dorm_min:   where.append("dormitorios_num >= :dmin");        params["dmin"] = dorm_min
    params["lim"] = min(int(limit or 40), 200)
    sql = text(f"select {_RED_COLS} from red_tokko_propiedades "
               f"where {' and '.join(where)} order by precio_num asc limit :lim")
    try:
        rows = [dict(r._mapping) for r in db.execute(sql, params)]
    except Exception:
        # Tabla aún no creada / sin datos en esta base.
        return {"total": 0, "propiedades": [],
                "nota": "No hay datos de la red Tokko en esta base. Corré la CLI tokko para poblarla."}

    # Marcar las que ya fueron importadas (dedup por ficha_url == link_externo)
    urls = [r["ficha_url"] for r in rows if r.get("ficha_url")]
    importadas = set()
    if urls:
        q = (db.query(mv.VentasPropiedad.link_externo)
             .filter(mv.VentasPropiedad.link_externo.in_(urls)))
        importadas = {x[0] for x in q}
    for r in rows:
        r["ya_importada"] = r.get("ficha_url") in importadas
    return {"total": len(rows), "propiedades": rows}


@router.post("/red-tokko/importar")
def red_tokko_importar(payload: dict,
                       db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Importa al catálogo (ventas_propiedades) las referencias indicadas."""
    v = get_vendedor(db, user)
    refs = payload.get("referencias") or []
    if not refs:
        raise HTTPException(400, "Enviá una lista 'referencias'.")
    sql = (text(f"select {_RED_COLS} from red_tokko_propiedades "
                "where referencia in :refs")
           .bindparams(bindparam("refs", expanding=True)))
    rows = [dict(r._mapping) for r in db.execute(sql, {"refs": refs})]

    creadas, saltadas, nuevas_props = 0, 0, []
    for r in rows:
        url = r.get("ficha_url")
        if url and db.query(mv.VentasPropiedad.id).filter_by(link_externo=url).first():
            saltadas += 1
            continue
        obj = mv.VentasPropiedad(
            titulo=r.get("direccion") or f"{r.get('tipo') or 'Propiedad'} en {r.get('ubicacion') or ''}".strip(),
            tipo=_enum(mv.VPropiedadTipo, _map_tokko_tipo(r.get("tipo")), "tipo"),
            estado=mv.VPropiedadEstado.disponible,
            fuente=mv.VPropiedadFuente.tokko,
            direccion=r.get("direccion"), ciudad=r.get("ubicacion"),
            lat=r.get("lat"), lng=r.get("lng"),
            precio_usd=r.get("precio_num"),
            dormitorios=r.get("dormitorios_num"), banos=r.get("banos_num"),
            descripcion=r.get("detalles"), inmobiliaria=r.get("publicado_por"),
            link_externo=url, cargada_por=v.id, is_demo=bool(v.is_demo),
        )
        db.add(obj)
        nuevas_props.append(obj)
        creadas += 1

    # Geo + barrio + matching para que aparezcan en el MAPA y en MATCHES.
    matches = _post_import_propiedades(db, nuevas_props)
    db.commit()
    return {"creadas": creadas, "saltadas_ya_existentes": saltadas,
            "pedidas": len(refs), "matches_generados": matches}


# ── Red Tokko EN VIVO: resolver zona (desambiguar) + traer por zona ──

@router.get("/red-tokko/zonas")
def red_tokko_zonas(q: str = Query(..., min_length=2),
                    db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Candidatos de ubicación para que el usuario elija el correcto.
    Ej: 'Santa Rosa' → [La Pampa|Capital|Santa Rosa, San Luis|…|Santa Rosa de Conlara, …]."""
    get_vendedor(db, user)
    from app.services import ventas_red_tokko
    try:
        return {"zonas": ventas_red_tokko.resolver_zonas(q)}
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception:
        raise HTTPException(502, "No se pudo consultar Tokko. Reintentá en un momento.")


@router.post("/red-tokko/buscar")
def red_tokko_buscar(payload: dict,
                     db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Trae EN VIVO de la red Tokko la zona elegida (loc_id/loc_type del
    endpoint /zonas), la guarda y la devuelve lista para importar."""
    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo un admin de ventas puede traer de la red en vivo.")
    loc_id = payload.get("loc_id")
    loc_type = payload.get("loc_type")
    if not loc_id:
        raise HTTPException(400, "Elegí una zona (loc_id) del autocomplete.")
    from app.services import ventas_red_tokko
    try:
        return ventas_red_tokko.buscar_en_vivo(
            db, loc_id=loc_id, loc_type=loc_type or "division",
            operacion=payload.get("operacion") or "venta",
            precio_min=payload.get("precio_min"), precio_max=payload.get("precio_max"),
            limit=min(int(payload.get("limit") or 60), 120),
            zona_nombre=payload.get("zona_nombre") or "",
            geocodificar=payload.get("geocodificar", True),
        )
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(502, f"No se pudo traer de la red: {str(e)[:200]}")
