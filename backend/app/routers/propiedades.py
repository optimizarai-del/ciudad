from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.security import get_current_user
from app import models, schemas

router = APIRouter(prefix="/api/propiedades", tags=["propiedades"])


@router.get("/", response_model=List[schemas.PropiedadOut])
def listar(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(models.Propiedad).order_by(models.Propiedad.id.desc()).all()


@router.post("/", response_model=schemas.PropiedadOut)
def crear(data: schemas.PropiedadCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = models.Propiedad(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.get("/{id}", response_model=schemas.PropiedadOut)
def detalle(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = db.query(models.Propiedad).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrada")
    return obj


@router.patch("/{id}", response_model=schemas.PropiedadOut)
def editar(id: int, data: schemas.PropiedadCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = db.query(models.Propiedad).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/{id}")
def eliminar(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = db.query(models.Propiedad).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrada")
    db.delete(obj); db.commit()
    return {"ok": True}
