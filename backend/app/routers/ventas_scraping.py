"""Router de scraping de webs inmobiliarias (Fase 4.1).

Endpoints (prefijo /api/ventas-scraping):
  GET  /fuentes               → catálogo de sitios soportados
  GET  /config                → config por fuente (admin)
  PUT  /config/{fuente}        → prender/apagar + parámetros (admin)
  POST /sync                  → encola (o corre sync) una pasada (admin)
  GET  /jobs                  → últimos jobs y su estado
  GET  /propiedades           → listar lo scrapeado (con filtros, igual que red-tokko)
  POST /importar              → importar al catálogo ventas_propiedades

La cola Redis se usa si REDIS_URL está configurada; si no, el sync corre
síncrono dentro del request (modo dev/local).
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models_ventas as mv
from app.routers.ventas_crm import get_vendedor, _enum, _post_import_propiedades
from app.services import ventas_scraping as scraping
from app.services.ventas_scraping import pipeline, queue as scraping_queue

router = APIRouter(prefix="/api/ventas-scraping", tags=["ventas-scraping"])

_TIPO_MAP = {
    "casa": "casa", "departamento": "departamento", "lote": "lote",
    "local": "local", "oficina": "oficina", "galpon": "galpon",
    "campo": "campo", "otro": "otro",
}


def _solo_admin(v):
    if not v.es_admin:
        raise HTTPException(403, "Solo un admin de ventas puede operar el scraping.")


# ───────────────────────── fuentes y config ─────────────────────────

@router.get("/fuentes")
def listar_fuentes(db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_vendedor(db, user)
    return {"fuentes": scraping.fuentes_disponibles()}


@router.get("/config")
def listar_config(db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    _solo_admin(v)
    out = []
    for info in scraping.fuentes_disponibles():
        cfg = pipeline.get_config(db, info["id"])
        out.append({
            **info,
            "activo": cfg.activo, "ciudad": cfg.ciudad,
            "operacion": cfg.operacion, "max_paginas": cfg.max_paginas,
            "sync_cada_horas": cfg.sync_cada_horas,
            "ultima_sync": cfg.ultima_sync.isoformat() if cfg.ultima_sync else None,
            "ultima_sync_resultado": json.loads(cfg.ultima_sync_resultado)
            if cfg.ultima_sync_resultado else None,
        })
    db.commit()
    return {"config": out}


@router.put("/config/{fuente}")
def actualizar_config(fuente: str, payload: dict,
                      db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    _solo_admin(v)
    if fuente not in scraping.ADAPTERS:
        raise HTTPException(404, f"Fuente desconocida: {fuente}")
    cfg = pipeline.get_config(db, fuente)
    for campo in ("activo", "ciudad", "operacion", "max_paginas",
                  "sync_cada_horas", "motor"):
        if campo in payload:
            setattr(cfg, campo, payload[campo])
    db.commit()
    return {"ok": True, "fuente": fuente}


# ───────────────────────── sync (cola o síncrono) ─────────────────────────

@router.post("/sync")
def sync(payload: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    _solo_admin(v)
    fuente = payload.get("fuente")
    if fuente not in scraping.ADAPTERS:
        raise HTTPException(400, f"Fuente inválida: {fuente}")
    cfg = pipeline.get_config(db, fuente)
    ciudad = payload.get("ciudad") or cfg.ciudad or "la-pampa"
    operacion = payload.get("operacion") or cfg.operacion or "venta"
    max_paginas = int(payload.get("max_paginas") or cfg.max_paginas or 5)

    job = mv.VentasScrapingJob(
        fuente=fuente, ciudad=ciudad, operacion=operacion,
        encolado_por=v.id, estado=mv.ScrapingJobEstado.encolado)
    db.add(job)
    db.commit()

    # ¿Hay cola Redis? → encolar. Si no, correr síncrono (dev/local).
    rq_id = scraping_queue.encolar(fuente, ciudad, operacion, max_paginas, job.id)
    if rq_id:
        job.rq_job_id = rq_id
        db.commit()
        return {"modo": "cola", "job_id": job.id, "rq_job_id": rq_id,
                "estado": "encolado"}

    # Modo síncrono
    job.estado = mv.ScrapingJobEstado.corriendo
    db.commit()
    try:
        resumen = pipeline.sincronizar(db, fuente, ciudad, operacion, max_paginas)
        job.estado = mv.ScrapingJobEstado.ok
        job.resultado = json.dumps(resumen, ensure_ascii=False)
    except Exception as e:
        job.estado = mv.ScrapingJobEstado.error
        job.error = str(e)[:2000]
        resumen = {"ok": False, "error": str(e)}
    job.finalizado_at = datetime.utcnow()
    db.commit()
    return {"modo": "sincrono", "job_id": job.id, **resumen}


@router.get("/jobs")
def listar_jobs(limit: int = Query(20),
                db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    _solo_admin(v)
    jobs = (db.query(mv.VentasScrapingJob)
            .order_by(mv.VentasScrapingJob.created_at.desc())
            .limit(min(int(limit or 20), 100)).all())
    out = []
    for j in jobs:
        estado = j.estado.value if hasattr(j.estado, "value") else j.estado
        # Refrescar estado desde RQ si el job sigue en vuelo
        if j.rq_job_id and estado in ("encolado", "corriendo"):
            rq_estado = scraping_queue.estado_job(j.rq_job_id)
            if rq_estado:
                estado = rq_estado
        out.append({
            "id": j.id, "fuente": j.fuente, "ciudad": j.ciudad,
            "operacion": j.operacion, "estado": estado,
            "resultado": json.loads(j.resultado) if j.resultado else None,
            "error": j.error,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "finalizado_at": j.finalizado_at.isoformat() if j.finalizado_at else None,
        })
    return {"jobs": out, "cola_disponible": scraping_queue.cola_disponible()}


# ───────────────────────── listar e importar ─────────────────────────

@router.get("/propiedades")
def listar_propiedades(
    fuente: Optional[str] = Query(None),
    zona: Optional[str] = Query(None),
    operacion: Optional[str] = Query(None),
    precio_min: Optional[int] = Query(None),
    precio_max: Optional[int] = Query(None),
    dorm_min: Optional[int] = Query(None),
    limit: int = Query(60),
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    get_vendedor(db, user)
    q = db.query(mv.VentasScrapingProp).filter(mv.VentasScrapingProp.activa.is_(True))
    if fuente:
        q = q.filter(mv.VentasScrapingProp.fuente == fuente)
    if operacion:
        q = q.filter(mv.VentasScrapingProp.operacion == operacion)
    if zona:
        q = q.filter(mv.VentasScrapingProp.ubicacion.ilike(f"%{zona}%"))
    if precio_min:
        q = q.filter(mv.VentasScrapingProp.precio_num >= precio_min)
    if precio_max:
        q = q.filter(mv.VentasScrapingProp.precio_num <= precio_max)
    if dorm_min:
        q = q.filter(mv.VentasScrapingProp.dormitorios_num >= dorm_min)
    rows = (q.order_by(mv.VentasScrapingProp.precio_num.asc())
            .limit(min(int(limit or 60), 200)).all())

    urls = [r.ficha_url for r in rows if r.ficha_url]
    importadas = set()
    if urls:
        importadas = {x[0] for x in db.query(mv.VentasPropiedad.link_externo)
                      .filter(mv.VentasPropiedad.link_externo.in_(urls))}
    props = []
    for r in rows:
        props.append({
            "referencia": r.referencia, "fuente": r.fuente,
            "direccion": r.direccion, "ubicacion": r.ubicacion,
            "tipo": r.tipo, "operacion": r.operacion,
            "precio_num": r.precio_num, "moneda": r.moneda,
            "precio_display": r.precio_display,
            "m2_cubierta_num": r.m2_cubierta_num, "m2_total_num": r.m2_total_num,
            "ambientes_num": r.ambientes_num, "dormitorios_num": r.dormitorios_num,
            "banos_num": r.banos_num, "lat": r.lat, "lng": r.lng,
            "detalles": r.detalles, "publicado_por": r.publicado_por,
            "ficha_url": r.ficha_url, "foto": r.foto,
            "ya_importada": r.ficha_url in importadas,
        })
    return {"total": len(props), "propiedades": props}


@router.post("/importar")
def importar(payload: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    refs = payload.get("referencias") or []
    if not refs:
        raise HTTPException(400, "Enviá una lista 'referencias'.")
    rows = (db.query(mv.VentasScrapingProp)
            .filter(mv.VentasScrapingProp.referencia.in_(refs)).all())

    creadas, saltadas, nuevas_props = 0, 0, []
    for r in rows:
        url = r.ficha_url
        if url and db.query(mv.VentasPropiedad.id).filter_by(link_externo=url).first():
            saltadas += 1
            continue
        obj = mv.VentasPropiedad(
            titulo=r.direccion or f"{r.tipo or 'Propiedad'} en {r.ubicacion or ''}".strip(),
            tipo=_enum(mv.VPropiedadTipo, _TIPO_MAP.get(r.tipo, "otro"), "tipo"),
            estado=mv.VPropiedadEstado.disponible,
            fuente=mv.VPropiedadFuente.scraping,
            direccion=r.direccion, ciudad=r.ubicacion,
            lat=r.lat, lng=r.lng, precio_usd=r.precio_num,
            dormitorios=r.dormitorios_num, banos=r.banos_num,
            descripcion=r.detalles, inmobiliaria=r.publicado_por,
            link_externo=url, cargada_por=v.id,
        )
        db.add(obj)
        nuevas_props.append(obj)
        r.importada = True
        creadas += 1

    # Geo + barrio + matching → aparecen en el MAPA y en MATCHES.
    matches = _post_import_propiedades(db, nuevas_props)
    db.commit()
    return {"creadas": creadas, "saltadas_ya_existentes": saltadas,
            "pedidas": len(refs), "matches_generados": matches}
