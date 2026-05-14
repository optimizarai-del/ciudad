from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.security import get_current_user
from app import models, schemas
from app.services import supabase_storage
from app.services.workspace import apply_workspace_filter, workspace_flag, is_demo_user

router = APIRouter(prefix="/api/propiedades", tags=["propiedades"])


def _to_out(p: models.Propiedad) -> dict:
    """Serialización con propietario_nombre para facilitar búsqueda/render en UI."""
    d = {c.name: getattr(p, c.name) for c in p.__table__.columns}
    nombre = None
    if p.propietario:
        partes = [p.propietario.nombre or "", p.propietario.apellido or ""]
        nombre = " ".join([s for s in partes if s]).strip() or None
    d["propietario_nombre"] = nombre
    return d


def _scope(db: Session, user):
    """Query base aislada por workspace (demo vs real)."""
    return apply_workspace_filter(db.query(models.Propiedad), models.Propiedad, user)


@router.get("/", response_model=List[schemas.PropiedadOut])
def listar(db: Session = Depends(get_db), user=Depends(get_current_user)):
    items = _scope(db, user).order_by(models.Propiedad.id.desc()).all()
    return [_to_out(p) for p in items]


@router.post("/", response_model=schemas.PropiedadOut)
def crear(data: schemas.PropiedadCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = models.Propiedad(**data.model_dump())
    obj.is_demo = workspace_flag(user)
    db.add(obj); db.commit(); db.refresh(obj)
    return _to_out(obj)


@router.get("/{id}", response_model=schemas.PropiedadOut)
def detalle(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = _scope(db, user).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrada")
    return _to_out(obj)


@router.patch("/{id}", response_model=schemas.PropiedadOut)
def editar(id: int, data: schemas.PropiedadCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = _scope(db, user).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        if k == "is_demo":  # no se puede cambiar el workspace via API
            continue
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return _to_out(obj)


@router.delete("/{id}")
def eliminar(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = _scope(db, user).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrada")
    db.delete(obj); db.commit()
    return {"ok": True}


class FichaPDFRequest(BaseModel):
    condiciones: Optional[str] = None


def _fotos_urls(db: Session, prop: models.Propiedad) -> list[str]:
    """URLs descargables de las fotos de la propiedad."""
    adj = (
        db.query(models.PropiedadAdjunto)
          .filter_by(propiedad_id=prop.id, tipo=models.AdjuntoTipo.foto)
          .order_by(
              models.PropiedadAdjunto.es_principal.desc(),
              models.PropiedadAdjunto.created_at.asc(),
          )
          .all()
    )
    urls = []
    for a in adj:
        if a.storage_path and supabase_storage.enabled():
            ok, signed = supabase_storage.get_signed_url(
                supabase_storage.BUCKET_ADJUNTOS, a.storage_path, expires_in=600,
            )
            if ok:
                urls.append(signed)
        # blob_b64 legacy: no soportado para el PDF (necesitaríamos un endpoint
        # auto-firmado, complica innecesariamente; los datos nuevos van a Storage).
    return urls


@router.post("/{id}/ficha-pdf")
def ficha_pdf(
    id: int,
    data: FichaPDFRequest = FichaPDFRequest(),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Genera un PDF de presentación del inmueble — fotos + características +
    condiciones. SIN propietarios ni inquilinos (es la versión comercial)."""
    p = _scope(db, user).filter_by(id=id).first()
    if not p:
        raise HTTPException(404, "Propiedad no encontrada")

    from app.services.pdf_ficha_inmueble import generar_pdf_ficha
    payload = {
        "tipo": p.tipo.value if hasattr(p.tipo, "value") else p.tipo,
        "direccion": p.direccion,
        "ciudad": p.ciudad,
        "provincia": p.provincia,
        "ambientes": p.ambientes,
        "superficie_m2": p.superficie_m2,
        "precio_alquiler": p.precio_alquiler,
        "expensas": p.expensas,
        "tasa_municipal": p.tasa_municipal,
        "descripcion": p.descripcion,
    }
    fotos = _fotos_urls(db, p)
    pdf = generar_pdf_ficha(payload, fotos, condiciones=data.condiciones)

    safe_addr = (p.direccion or f"propiedad-{p.id}").replace(" ", "-")[:60]
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="ficha-{safe_addr}.pdf"',
        },
    )
