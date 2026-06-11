"""
Router de Fase 2 (Tokko, Telegram, NLU) y Fase 3 (matches, tareas, post-venta).
Mismo prefijo /api/ventas-crm, mismas reglas de scoping que ventas_crm.
"""
import os
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models_ventas as mv, schemas_ventas as sv
from app.routers.ventas_crm import get_vendedor, _scope
from app.services import (
    ventas_tokko, ventas_telegram, ventas_nlu, ventas_jobs, ventas_tareas,
)

router = APIRouter(prefix="/api/ventas-crm", tags=["ventas-fase23"])


def _enum(EnumCls, value, field):
    if value is None:
        return None
    try:
        return EnumCls(value)
    except ValueError:
        ops = ", ".join(e.value for e in EnumCls)
        raise HTTPException(400, f"{field} inválido: '{value}'. Opciones: {ops}")


# ═══════════════ Matches (Fase 3 · Mod #8) ═══════════════

@router.get("/matches")
def listar_matches(orden: str = "score", db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Datos para la pantalla visual de matches (Mod #8): agrupados por
    propiedad, con los pedidos/clientes que matchean a la derecha."""
    v = get_vendedor(db, user)
    q = db.query(mv.VentasMatch).filter(mv.VentasMatch.estado != mv.MatchEstado.descartado)
    if not v.es_admin:
        q = q.filter(mv.VentasMatch.vendedor_id == v.id)
    matches = q.all()

    # Cache de propiedades, pedidos y clientes para no consultar 1x1
    props = {p.id: p for p in db.query(mv.VentasPropiedad).all()}
    pedidos = {p.id: p for p in db.query(mv.VentasPedido).all()}
    clientes = {c.id: c for c in db.query(mv.VentasCliente).all()}

    por_prop = {}
    for m in matches:
        prop = props.get(m.propiedad_id)
        ped = pedidos.get(m.pedido_id)
        if not prop or not ped:
            continue
        cli = clientes.get(ped.cliente_id)
        entry = por_prop.setdefault(prop.id, {
            "propiedad": {
                "id": prop.id, "titulo": prop.titulo, "direccion": prop.direccion,
                "ciudad": prop.ciudad, "tipo": prop.tipo.value if prop.tipo else None,
                "precio_usd": prop.precio_usd, "superficie_m2": prop.superficie_m2,
                "dormitorios": prop.dormitorios, "banos": prop.banos,
                "fuente": prop.fuente.value if prop.fuente else None,
            },
            "matches": [],
        })
        entry["matches"].append({
            "match_id": m.id, "pedido_id": ped.id, "cliente_id": ped.cliente_id,
            "cliente_nombre": cli.nombre if cli else f"Cliente #{ped.cliente_id}",
            "score": m.score, "estado": m.estado.value if m.estado else "pendiente",
            "razones": json.loads(m.razones_json) if m.razones_json else [],
        })

    grupos = list(por_prop.values())
    for g in grupos:
        g["matches"].sort(key=lambda x: x["score"], reverse=True)
        g["max_score"] = g["matches"][0]["score"] if g["matches"] else 0
    grupos.sort(key=lambda g: g["max_score"], reverse=True)
    return {"grupos": grupos, "total_matches": len(matches)}


@router.patch("/matches/{mid}")
def cambiar_estado_match(mid: int, estado: str = Query(...),
                         db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    m = db.query(mv.VentasMatch).filter_by(id=mid).first()
    if not m:
        raise HTTPException(404, "Match no encontrado")
    if not v.es_admin and m.vendedor_id != v.id:
        raise HTTPException(403, "No es tu match")
    m.estado = _enum(mv.MatchEstado, estado, "estado")
    db.commit()
    return {"ok": True, "estado": m.estado.value}


# ═══════════════ Tareas (Fase 3) ═══════════════

@router.get("/tareas", response_model=List[sv.TareaOut])
def listar_tareas(estado: Optional[str] = None,
                  db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    q = _scope(db.query(mv.VentasTarea), mv.VentasTarea, v)
    if estado:
        q = q.filter(mv.VentasTarea.estado == _enum(mv.TareaEstado, estado, "estado"))
    return q.order_by(mv.VentasTarea.vencimiento.asc().nullslast()).all()


@router.post("/tareas", response_model=sv.TareaOut)
def crear_tarea(data: sv.TareaCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    obj = mv.VentasTarea(
        vendedor_id=v.id, cliente_id=data.cliente_id,
        tipo=_enum(mv.TareaTipo, data.tipo, "tipo"),
        descripcion=data.descripcion, vencimiento=data.vencimiento,
        estado=mv.TareaEstado.pendiente,
    )
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.patch("/tareas/{tid}/hecha", response_model=sv.TareaOut)
def marcar_tarea_hecha(tid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    obj = _scope(db.query(mv.VentasTarea), mv.VentasTarea, v).filter_by(id=tid).first()
    if not obj:
        raise HTTPException(404, "Tarea no encontrada")
    obj.estado = mv.TareaEstado.hecha
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/tareas/{tid}")
def eliminar_tarea(tid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    obj = _scope(db.query(mv.VentasTarea), mv.VentasTarea, v).filter_by(id=tid).first()
    if not obj:
        raise HTTPException(404, "Tarea no encontrada")
    db.delete(obj); db.commit()
    return {"ok": True}


# ═══════════════ Plantillas de seguimiento (Fase 3) ═══════════════

@router.get("/plantillas", response_model=List[sv.PlantillaOut])
def listar_plantillas(db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_vendedor(db, user)
    ventas_tareas.asegurar_plantillas_default(db); db.commit()
    return db.query(mv.VentasPlantillaSeguimiento).order_by(mv.VentasPlantillaSeguimiento.offset_dias).all()


@router.post("/plantillas", response_model=sv.PlantillaOut)
def crear_plantilla(data: sv.PlantillaCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo el admin gestiona plantillas")
    obj = mv.VentasPlantillaSeguimiento(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.patch("/plantillas/{pid}", response_model=sv.PlantillaOut)
def editar_plantilla(pid: int, data: sv.PlantillaCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo el admin gestiona plantillas")
    obj = db.query(mv.VentasPlantillaSeguimiento).filter_by(id=pid).first()
    if not obj:
        raise HTTPException(404, "Plantilla no encontrada")
    for k, val in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, val)
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/plantillas/{pid}")
def eliminar_plantilla(pid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo el admin gestiona plantillas")
    obj = db.query(mv.VentasPlantillaSeguimiento).filter_by(id=pid).first()
    if not obj:
        raise HTTPException(404, "Plantilla no encontrada")
    db.delete(obj); db.commit()
    return {"ok": True}


# ═══════════════ Tokko (Fase 2 · Mod #7) ═══════════════

def _tokko_out(cfg) -> dict:
    try:
        ciudades = json.loads(cfg.ciudades_json) if cfg.ciudades_json else []
    except Exception:
        ciudades = []
    return {
        "activo": cfg.activo, "tiene_api_key": bool(cfg.api_key),
        "ciudades": ciudades, "sync_cada_horas": cfg.sync_cada_horas or 4,
        "ultima_sync": cfg.ultima_sync, "ultima_sync_resultado": cfg.ultima_sync_resultado,
    }


@router.get("/tokko-config", response_model=sv.TokkoConfigOut)
def get_tokko_config(db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_vendedor(db, user)
    return _tokko_out(ventas_tokko.get_config(db))


@router.put("/tokko-config", response_model=sv.TokkoConfigOut)
def set_tokko_config(data: sv.TokkoConfigIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo el admin configura Tokko")
    cfg = ventas_tokko.get_config(db)
    if data.api_key is not None:
        cfg.api_key = data.api_key or None
    if data.activo is not None:
        cfg.activo = data.activo
    if data.ciudades is not None:
        cfg.ciudades_json = json.dumps(data.ciudades, ensure_ascii=False)
    if data.sync_cada_horas is not None:
        cfg.sync_cada_horas = data.sync_cada_horas
    db.commit(); db.refresh(cfg)
    return _tokko_out(cfg)


@router.post("/tokko-sync")
def tokko_sync(db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    if not v.es_admin:
        raise HTTPException(403, "Solo el admin sincroniza Tokko")
    resultado = ventas_tokko.sincronizar(db)
    db.commit()
    return resultado


# ═══════════════ Telegram (Fase 2) ═══════════════

@router.get("/telegram/estado")
def telegram_estado(db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    link = db.query(mv.VentasTelegramLink).filter_by(vendedor_id=v.id).first()
    return {
        "vinculado": bool(link and link.vinculado),
        "bot_disponible": ventas_telegram.bot_disponible(),
    }


@router.post("/telegram/generar-token")
def telegram_generar_token(db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    res = ventas_telegram.generar_token_vinculacion(db, v.id)
    db.commit()
    return res


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """Receptor del webhook de Telegram. Sin auth (lo llama Telegram).
    Maneja la vinculación con /start <token>."""
    try:
        update = await request.json()
    except Exception:
        return {"ok": True}
    msg = update.get("message") or update.get("edited_message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    texto = (msg.get("text") or "").strip()
    if texto.startswith("/start") and chat_id is not None:
        partes = texto.split(maxsplit=1)
        if len(partes) == 2:
            ok = ventas_telegram.confirmar_vinculacion(db, partes[1].strip(), chat_id)
            db.commit()
            if ok:
                ventas_telegram._enviar_mensaje(chat_id, "✅ Vinculado a CIUDAD Ventas. Vas a recibir tus notificaciones acá.")
            else:
                ventas_telegram._enviar_mensaje(chat_id, "❌ Token inválido o vencido. Generá uno nuevo desde la web.")
    return {"ok": True}


# ═══════════════ NLU (Fase 2) ═══════════════

@router.post("/ai/parse-pedido")
def parse_pedido(data: sv.NLURequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_vendedor(db, user)
    return ventas_nlu.parsear_pedido(data.texto)


# ═══════════════ Notificaciones (Fase 2/3) ═══════════════

@router.get("/notificaciones", response_model=List[sv.NotificacionOut])
def listar_notificaciones(solo_no_leidas: bool = False,
                          db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    q = db.query(mv.VentasNotificacion).filter_by(vendedor_id=v.id)
    if solo_no_leidas:
        q = q.filter(mv.VentasNotificacion.leida == False)  # noqa: E712
    return q.order_by(mv.VentasNotificacion.created_at.desc()).limit(100).all()


@router.post("/notificaciones/{nid}/leida")
def marcar_notif_leida(nid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    n = db.query(mv.VentasNotificacion).filter_by(id=nid, vendedor_id=v.id).first()
    if not n:
        raise HTTPException(404, "Notificación no encontrada")
    n.leida = True
    db.commit()
    return {"ok": True}


@router.post("/notificaciones/marcar-todas")
def marcar_todas_leidas(db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    db.query(mv.VentasNotificacion).filter_by(vendedor_id=v.id, leida=False).update({"leida": True})
    db.commit()
    return {"ok": True}


# ═══════════════ Jobs diarios (Fase 3) ═══════════════

@router.post("/jobs/run-daily")
def run_daily_jobs(token: Optional[str] = None, hora: Optional[str] = None,
                   db: Session = Depends(get_db)):
    """Cron de Easypanel pega acá. Protegido por VENTAS_JOB_TOKEN (si está
    seteado). `hora` (HH) hace que solo notifique a vendedores con esa hora."""
    secreto = os.getenv("VENTAS_JOB_TOKEN", "").strip()
    if secreto and token != secreto:
        raise HTTPException(403, "Token de job inválido")
    return ventas_jobs.run_daily(db, hora=hora)
