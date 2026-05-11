"""
Migración de blobs legacy (base64 inline en la DB) a Supabase Storage.

  POST /api/admin/storage/migrar           — migra adjuntos + comprobantes
  GET  /api/admin/storage/estado           — cuántos faltan migrar
  POST /api/admin/storage/ensure-buckets   — fuerza creación de buckets

Sólo admin. Idempotente — corre sobre filas que tienen blob pero no
storage_path. Después de subir limpia el blob (NULL) para liberar la DB.
"""
import base64
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models
from app.services import supabase_storage


router = APIRouter(prefix="/api/admin/storage", tags=["admin"])


def _require_admin(user):
    if user.role != models.UserRole.admin:
        raise HTTPException(403, "Solo admin")


@router.get("/estado")
def estado(db: Session = Depends(get_db), user=Depends(get_current_user)):
    _require_admin(user)
    adj_pendientes = (
        db.query(models.PropiedadAdjunto)
          .filter(models.PropiedadAdjunto.storage_path.is_(None),
                  models.PropiedadAdjunto.blob_b64.isnot(None),
                  models.PropiedadAdjunto.blob_b64 != "")
          .count()
    )
    comp_pendientes = (
        db.query(models.Comprobante)
          .filter(models.Comprobante.storage_path.is_(None),
                  models.Comprobante.pdf_blob.isnot(None),
                  models.Comprobante.pdf_blob != "")
          .count()
    )
    return {
        "storage_habilitado": supabase_storage.enabled(),
        "adjuntos_pendientes": adj_pendientes,
        "comprobantes_pendientes": comp_pendientes,
    }


@router.post("/ensure-buckets")
def ensure_buckets(user=Depends(get_current_user)):
    _require_admin(user)
    ok, msg = supabase_storage.ensure_buckets()
    return {"ok": ok, "mensaje": msg}


@router.post("/migrar")
def migrar(
    limite: int = 100,
    purgar_blob: bool = True,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Sube a Storage los blobs viejos. Procesa hasta `limite` filas de cada
    tipo por llamada (para no bloquear request por horas).

    `purgar_blob=True` (default): después de subir limpia `blob_b64`/`pdf_blob`
    a NULL para liberar espacio en la DB.
    """
    _require_admin(user)
    if not supabase_storage.enabled():
        raise HTTPException(400, "Supabase Storage no está configurado")

    adj_ok = 0
    adj_fail = 0
    comp_ok = 0
    comp_fail = 0
    errores = []

    # Adjuntos
    pendientes_adj = (
        db.query(models.PropiedadAdjunto)
          .filter(models.PropiedadAdjunto.storage_path.is_(None),
                  models.PropiedadAdjunto.blob_b64.isnot(None),
                  models.PropiedadAdjunto.blob_b64 != "")
          .limit(limite)
          .all()
    )
    for a in pendientes_adj:
        try:
            raw = base64.b64decode(a.blob_b64)
        except Exception as e:
            adj_fail += 1
            errores.append(f"adj#{a.id} decode: {e}")
            continue
        path = supabase_storage.gen_path(f"prop-{a.propiedad_id}", a.nombre_archivo)
        ok, info = supabase_storage.upload(
            supabase_storage.BUCKET_ADJUNTOS, path, raw, a.mime or "application/octet-stream",
        )
        if ok:
            a.storage_path = info
            if purgar_blob:
                a.blob_b64 = None
            adj_ok += 1
        else:
            adj_fail += 1
            errores.append(f"adj#{a.id} upload: {info}")
    db.commit()

    # Comprobantes
    pendientes_comp = (
        db.query(models.Comprobante)
          .filter(models.Comprobante.storage_path.is_(None),
                  models.Comprobante.pdf_blob.isnot(None),
                  models.Comprobante.pdf_blob != "")
          .limit(limite)
          .all()
    )
    for c in pendientes_comp:
        try:
            raw = base64.b64decode(c.pdf_blob)
        except Exception as e:
            comp_fail += 1
            errores.append(f"comp#{c.id} decode: {e}")
            continue
        path = supabase_storage.gen_path(f"pago-{c.pago_id}", f"{c.tipo.value if hasattr(c.tipo,'value') else c.tipo}.pdf")
        ok, info = supabase_storage.upload(
            supabase_storage.BUCKET_COMPROBANTES, path, raw, "application/pdf",
        )
        if ok:
            c.storage_path = info
            if purgar_blob:
                c.pdf_blob = None
            comp_ok += 1
        else:
            comp_fail += 1
            errores.append(f"comp#{c.id} upload: {info}")
    db.commit()

    return {
        "adjuntos": {"migrados": adj_ok, "fallidos": adj_fail},
        "comprobantes": {"migrados": comp_ok, "fallidos": comp_fail},
        "errores": errores[:20],
    }
