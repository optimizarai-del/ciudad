"""Radar Instagram (Fase 4.7).

Seguimiento de cuentas de Instagram que publican propiedades. Se cargan los
usernames a seguir, una vez al día (o a mano) se scrapean sus publicaciones y
quedan listadas para analizar.

Endpoints (prefijo /api/ventas-instagram):
  GET    /cuentas                     → cuentas seguidas (scoped por demo)
  POST   /cuentas                     → agregar una cuenta (admin)
  PATCH  /cuentas/{id}                → editar (activa/nombre/notas) (admin)
  DELETE /cuentas/{id}                → borrar cuenta + sus publicaciones (admin)
  POST   /cuentas/{id}/scrapear       → correr ahora una cuenta (admin)
  POST   /scrapear                    → correr ahora todas las activas (admin)
  GET    /publicaciones               → listar posts traídos (con filtros)
  POST   /jobs/run-daily              → corrida diaria (token, para cron externo)

Fuente: Apify (modo mock sin APIFY_TOKEN). Ver services/ventas_instagram.py.
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models_ventas as mv
from app.routers.ventas_crm import get_vendedor, _demo
from app.services import ventas_instagram as ig

router = APIRouter(prefix="/api/ventas-instagram", tags=["ventas-instagram"])


def _solo_admin(v):
    if not v.es_admin:
        raise HTTPException(403, "Solo un admin de ventas puede gestionar el radar de Instagram.")


class CuentaIn(BaseModel):
    username: str
    nombre: Optional[str] = None
    activa: Optional[bool] = True
    notas: Optional[str] = None


class CuentaUpdate(BaseModel):
    nombre: Optional[str] = None
    activa: Optional[bool] = None
    notas: Optional[str] = None


class PublicacionUpdate(BaseModel):
    notas: Optional[str] = None


def _cuenta_dict(c: mv.IgCuenta) -> dict:
    return {
        "id": c.id,
        "username": c.username,
        "nombre": c.nombre,
        "activa": bool(c.activa),
        "notas": c.notas,
        "ultima_corrida": c.ultima_corrida.isoformat() if c.ultima_corrida else None,
        "ultimo_estado": c.ultimo_estado,
        "ultimo_nuevas": c.ultimo_nuevas or 0,
    }


def _pub_dict(p: mv.IgPublicacion) -> dict:
    return {
        "id": p.id,
        "cuenta_id": p.cuenta_id,
        "url": p.url,
        "caption": p.caption,
        "imagen_url": p.imagen_url,
        "tipo": p.tipo,
        "fecha_post": p.fecha_post.isoformat() if p.fecha_post else None,
        "likes": p.likes or 0,
        "comentarios": p.comentarios or 0,
        "autor_username": p.autor_username,
        "autor_nombre": p.autor_nombre,
        "autor_foto": p.autor_foto,
        "operacion": p.operacion,
        "precio_texto": p.precio_texto,
        "notas": p.notas,
        "scraped_at": p.scraped_at.isoformat() if p.scraped_at else None,
    }


# ───────────────────────── Cuentas ─────────────────────────

@router.get("/cuentas")
def listar_cuentas(db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    q = _demo(db.query(mv.IgCuenta), mv.IgCuenta, v).order_by(mv.IgCuenta.id.desc())
    return [_cuenta_dict(c) for c in q.all()]


@router.post("/cuentas")
def crear_cuenta(data: CuentaIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    _solo_admin(v)
    username = (data.username or "").strip().lstrip("@").lower()
    if not username:
        raise HTTPException(400, "El usuario de Instagram es obligatorio.")
    # Evitar duplicados dentro del mismo workspace demo/real.
    ya = _demo(db.query(mv.IgCuenta), mv.IgCuenta, v).filter(mv.IgCuenta.username == username).first()
    if ya:
        raise HTTPException(400, f"La cuenta @{username} ya está en el radar.")
    c = mv.IgCuenta(
        username=username,
        nombre=(data.nombre or "").strip() or None,
        activa=data.activa if data.activa is not None else True,
        notas=data.notas,
        is_demo=bool(v.is_demo),
        creada_por=v.id,
    )
    db.add(c); db.commit(); db.refresh(c)
    return _cuenta_dict(c)


@router.patch("/cuentas/{cuenta_id}")
def editar_cuenta(cuenta_id: int, data: CuentaUpdate,
                  db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    _solo_admin(v)
    c = _demo(db.query(mv.IgCuenta), mv.IgCuenta, v).filter(mv.IgCuenta.id == cuenta_id).first()
    if not c:
        raise HTTPException(404, "Cuenta no encontrada")
    for k, val in data.model_dump(exclude_unset=True).items():
        setattr(c, k, val)
    db.commit(); db.refresh(c)
    return _cuenta_dict(c)


@router.delete("/cuentas/{cuenta_id}", status_code=204)
def borrar_cuenta(cuenta_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    _solo_admin(v)
    c = _demo(db.query(mv.IgCuenta), mv.IgCuenta, v).filter(mv.IgCuenta.id == cuenta_id).first()
    if not c:
        raise HTTPException(404, "Cuenta no encontrada")
    db.query(mv.IgPublicacion).filter(mv.IgPublicacion.cuenta_id == c.id).delete()
    db.delete(c)
    db.commit()
    return None


# ───────────────────────── Scrapear ─────────────────────────

@router.post("/cuentas/{cuenta_id}/scrapear")
def scrapear_una(cuenta_id: int, limite: Optional[int] = None,
                 operacion: Optional[str] = None, q: Optional[str] = None,
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Corre el scraper de una cuenta. `operacion` ('venta'|'alquiler') y `q`
    (palabra clave) filtran los posts ANTES de guardarlos."""
    v = get_vendedor(db, user)
    _solo_admin(v)
    c = _demo(db.query(mv.IgCuenta), mv.IgCuenta, v).filter(mv.IgCuenta.id == cuenta_id).first()
    if not c:
        raise HTTPException(404, "Cuenta no encontrada")
    resumen = ig.correr_scrape(db, [c], limite, operacion=operacion, q=q)
    db.commit()
    return resumen


@router.post("/scrapear")
def scrapear_todas(limite: Optional[int] = None,
                   operacion: Optional[str] = None, q: Optional[str] = None,
                   db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Corre el scraper de todas las cuentas activas. `operacion` y `q` filtran
    los posts ANTES de guardarlos (solo se traen los que matchean)."""
    v = get_vendedor(db, user)
    _solo_admin(v)
    cuentas = _demo(db.query(mv.IgCuenta), mv.IgCuenta, v).filter(mv.IgCuenta.activa.is_(True)).all()
    if not cuentas:
        return {"cuentas": 0, "nuevas": 0, "usando_mock": True, "detalle": []}
    resumen = ig.correr_scrape(db, cuentas, limite, operacion=operacion, q=q)
    db.commit()
    return resumen


# ───────────────────────── Publicaciones ─────────────────────────

@router.get("/publicaciones")
def listar_publicaciones(cuenta_id: Optional[int] = None, operacion: Optional[str] = None,
                         q: Optional[str] = None, skip: int = 0,
                         limit: int = Query(60, le=200),
                         db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = get_vendedor(db, user)
    query = _demo(db.query(mv.IgPublicacion), mv.IgPublicacion, v)
    if cuenta_id:
        query = query.filter(mv.IgPublicacion.cuenta_id == cuenta_id)
    if operacion:
        query = query.filter(mv.IgPublicacion.operacion == operacion)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            (mv.IgPublicacion.caption.ilike(like))
            | (mv.IgPublicacion.autor_username.ilike(like))
        )
    total = query.count()
    rows = (
        query.order_by(mv.IgPublicacion.fecha_post.desc(), mv.IgPublicacion.id.desc())
        .offset(skip).limit(limit).all()
    )
    return {"total": total, "publicaciones": [_pub_dict(p) for p in rows]}


@router.get("/publicaciones/{pub_id}")
def ver_publicacion(pub_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Ficha de una publicación."""
    v = get_vendedor(db, user)
    p = _demo(db.query(mv.IgPublicacion), mv.IgPublicacion, v).filter(
        mv.IgPublicacion.id == pub_id).first()
    if not p:
        raise HTTPException(404, "Publicación no encontrada")
    return _pub_dict(p)


@router.patch("/publicaciones/{pub_id}")
def editar_publicacion(pub_id: int, data: PublicacionUpdate,
                       db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Guarda las notas del equipo sobre una publicación. Cualquier usuario de
    ventas puede anotar (no solo admin)."""
    v = get_vendedor(db, user)
    p = _demo(db.query(mv.IgPublicacion), mv.IgPublicacion, v).filter(
        mv.IgPublicacion.id == pub_id).first()
    if not p:
        raise HTTPException(404, "Publicación no encontrada")
    for k, val in data.model_dump(exclude_unset=True).items():
        setattr(p, k, val)
    db.commit(); db.refresh(p)
    return _pub_dict(p)


# ───────────────────────── Job diario (cron externo) ─────────────────────────

@router.post("/jobs/run-daily")
def run_daily(token: Optional[str] = None, limite: Optional[int] = None,
              db: Session = Depends(get_db)):
    """Corrida diaria de todas las cuentas activas (todos los workspaces).
    Pensado para dispararse desde un cron de Easypanel. Protegido por
    VENTAS_JOB_TOKEN si está configurado."""
    secreto = os.getenv("VENTAS_JOB_TOKEN", "").strip()
    if secreto and token != secreto:
        raise HTTPException(403, "Token de job inválido")
    # Corrida automática: solo cuentas reales (el demo se scrapea a mano).
    cuentas = db.query(mv.IgCuenta).filter(
        mv.IgCuenta.activa.is_(True), mv.IgCuenta.is_demo.is_(False)
    ).all()
    if not cuentas:
        return {"cuentas": 0, "nuevas": 0, "usando_mock": True, "detalle": []}
    resumen = ig.correr_scrape(db, cuentas, limite)
    db.commit()
    return resumen
