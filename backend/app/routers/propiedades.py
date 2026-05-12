from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.security import get_current_user
from app import models, schemas

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


@router.get("/", response_model=List[schemas.PropiedadOut])
def listar(db: Session = Depends(get_db), user=Depends(get_current_user)):
    items = db.query(models.Propiedad).order_by(models.Propiedad.id.desc()).all()
    return [_to_out(p) for p in items]


@router.post("/", response_model=schemas.PropiedadOut)
def crear(data: schemas.PropiedadCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = models.Propiedad(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return _to_out(obj)


@router.get("/{id}", response_model=schemas.PropiedadOut)
def detalle(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = db.query(models.Propiedad).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrada")
    return _to_out(obj)


@router.patch("/{id}", response_model=schemas.PropiedadOut)
def editar(id: int, data: schemas.PropiedadCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = db.query(models.Propiedad).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return _to_out(obj)


@router.delete("/{id}")
def eliminar(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = db.query(models.Propiedad).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrada")
    db.delete(obj); db.commit()
    return {"ok": True}
