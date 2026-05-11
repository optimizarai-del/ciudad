"""
Adjuntos por propiedad (fotos / documentos / planos).

  GET    /api/propiedades/{id}/adjuntos             — lista (sin blobs).
  POST   /api/propiedades/{id}/adjuntos             — sube uno (multipart o JSON b64).
  GET    /api/propiedades/{id}/adjuntos/{aid}       — descarga (binario).
  PATCH  /api/propiedades/{id}/adjuntos/{aid}       — descripción / tipo / es_principal.
  DELETE /api/propiedades/{id}/adjuntos/{aid}
"""
import base64
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models
from app.services import supabase_storage


router = APIRouter(prefix="/api/propiedades", tags=["adjuntos"])


# Límite por archivo (MB). Suficiente para fotos comprimidas y PDFs livianos.
MAX_BYTES = 8 * 1024 * 1024


def _serialize(a: models.PropiedadAdjunto) -> dict:
    return {
        "id": a.id,
        "propiedad_id": a.propiedad_id,
        "tipo": a.tipo.value if hasattr(a.tipo, "value") else a.tipo,
        "nombre_archivo": a.nombre_archivo,
        "mime": a.mime,
        "tamano_bytes": a.tamano_bytes,
        "descripcion": a.descripcion,
        "es_principal": a.es_principal,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/{prop_id}/adjuntos")
def listar(prop_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    prop = db.query(models.Propiedad).filter_by(id=prop_id).first()
    if not prop:
        raise HTTPException(404, "Propiedad no encontrada")
    adj = (
        db.query(models.PropiedadAdjunto)
        .filter_by(propiedad_id=prop_id)
        .order_by(models.PropiedadAdjunto.es_principal.desc(),
                  models.PropiedadAdjunto.created_at.desc())
        .all()
    )
    return [_serialize(a) for a in adj]


class AdjuntoCreateJSON(BaseModel):
    nombre_archivo: str
    mime: Optional[str] = "application/octet-stream"
    tipo: Optional[str] = "foto"
    descripcion: Optional[str] = None
    contenido_b64: str   # base64 sin prefijo data:


@router.post("/{prop_id}/adjuntos")
async def subir(
    prop_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    archivo: Optional[UploadFile] = File(None),
    tipo: str = Form("foto"),
    descripcion: Optional[str] = Form(None),
    es_principal: bool = Form(False),
    json_data: Optional[AdjuntoCreateJSON] = None,
):
    """Acepta multipart/form-data (archivo) o JSON con contenido_b64."""
    prop = db.query(models.Propiedad).filter_by(id=prop_id).first()
    if not prop:
        raise HTTPException(404, "Propiedad no encontrada")

    # Camino A: multipart con UploadFile
    if archivo is not None:
        raw = await archivo.read()
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, f"Archivo > {MAX_BYTES // 1024 // 1024} MB")
        nombre = archivo.filename or "archivo"
        mime = archivo.content_type or "application/octet-stream"
        b64 = base64.b64encode(raw).decode("ascii")
        size = len(raw)
        desc = descripcion
    elif json_data is not None:
        # Camino B: JSON con base64 ya decodificado
        try:
            raw = base64.b64decode(json_data.contenido_b64, validate=True)
        except Exception:
            raise HTTPException(400, "contenido_b64 inválido")
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, f"Archivo > {MAX_BYTES // 1024 // 1024} MB")
        nombre = json_data.nombre_archivo
        mime = json_data.mime or "application/octet-stream"
        b64 = json_data.contenido_b64
        size = len(raw)
        tipo = json_data.tipo or tipo
        desc = json_data.descripcion or descripcion
    else:
        raise HTTPException(400, "Falta archivo (multipart) o body JSON con contenido_b64")

    valido = [t.value for t in models.AdjuntoTipo]
    if tipo not in valido:
        tipo = "otro"

    # Si pidieron es_principal, desmarcar el resto
    if es_principal:
        db.query(models.PropiedadAdjunto).filter_by(
            propiedad_id=prop_id, es_principal=True
        ).update({"es_principal": False})

    # Si Supabase Storage está habilitado, subir el blob ahí y guardar solo
    # la ruta. Fallback: guardar base64 en la DB (modo legacy).
    storage_path = None
    blob_para_db: Optional[str] = b64
    if supabase_storage.enabled():
        path = supabase_storage.gen_path(f"prop-{prop_id}", nombre)
        ok, info = supabase_storage.upload(
            supabase_storage.BUCKET_ADJUNTOS, path, raw, mime,
        )
        if ok:
            storage_path = info
            blob_para_db = None
        else:
            # Si Storage falla por algún motivo (ej. red), caer al legacy en vez
            # de bloquear al usuario subiendo el archivo.
            print(f"[adjuntos] Storage upload falló: {info} — fallback a base64")

    a = models.PropiedadAdjunto(
        propiedad_id=prop_id,
        tipo=tipo,
        nombre_archivo=nombre,
        mime=mime,
        tamano_bytes=size,
        descripcion=desc,
        blob_b64=blob_para_db,
        storage_path=storage_path,
        es_principal=es_principal,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _serialize(a)


@router.get("/{prop_id}/adjuntos/{aid}")
def descargar(prop_id: int, aid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    a = db.query(models.PropiedadAdjunto).filter_by(id=aid, propiedad_id=prop_id).first()
    if not a:
        raise HTTPException(404, "Adjunto no encontrado")

    # Modo Storage: redirigir a una URL firmada (1h)
    if a.storage_path and supabase_storage.enabled():
        ok, signed = supabase_storage.get_signed_url(
            supabase_storage.BUCKET_ADJUNTOS, a.storage_path, expires_in=3600,
        )
        if ok:
            return RedirectResponse(url=signed, status_code=307)
        # Si falla el sign, intentamos legacy si todavía está el blob
        print(f"[adjuntos] sign falló: {signed} — intentando blob legacy")

    # Modo legacy: blob inline en la DB
    if not a.blob_b64:
        raise HTTPException(404, "Contenido no disponible")
    raw = base64.b64decode(a.blob_b64)
    return Response(
        content=raw,
        media_type=a.mime or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{a.nombre_archivo}"'},
    )


class AdjuntoPatchIn(BaseModel):
    descripcion: Optional[str] = None
    tipo: Optional[str] = None
    es_principal: Optional[bool] = None


@router.patch("/{prop_id}/adjuntos/{aid}")
def editar(prop_id: int, aid: int, data: AdjuntoPatchIn,
           db: Session = Depends(get_db), user=Depends(get_current_user)):
    a = db.query(models.PropiedadAdjunto).filter_by(id=aid, propiedad_id=prop_id).first()
    if not a:
        raise HTTPException(404, "Adjunto no encontrado")
    if data.descripcion is not None:
        a.descripcion = data.descripcion
    if data.tipo:
        valido = [t.value for t in models.AdjuntoTipo]
        if data.tipo in valido:
            a.tipo = data.tipo
    if data.es_principal is True:
        db.query(models.PropiedadAdjunto).filter_by(
            propiedad_id=prop_id, es_principal=True
        ).update({"es_principal": False})
        a.es_principal = True
    elif data.es_principal is False:
        a.es_principal = False
    db.commit()
    db.refresh(a)
    return _serialize(a)


@router.delete("/{prop_id}/adjuntos/{aid}")
def eliminar(prop_id: int, aid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    a = db.query(models.PropiedadAdjunto).filter_by(id=aid, propiedad_id=prop_id).first()
    if not a:
        raise HTTPException(404, "Adjunto no encontrado")

    # Si vivía en Storage, borrarlo allá también (best-effort; si falla
    # seguimos con el delete de la DB).
    if a.storage_path and supabase_storage.enabled():
        ok, info = supabase_storage.delete(supabase_storage.BUCKET_ADJUNTOS, a.storage_path)
        if not ok:
            print(f"[adjuntos] Storage delete falló: {info}")

    db.delete(a)
    db.commit()
    return {"ok": True}
