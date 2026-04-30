from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.security import get_current_user
from app import models, schemas

router = APIRouter(prefix="/api/contratos", tags=["contratos"])


@router.get("/", response_model=List[schemas.ContratoOut])
def listar(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(models.Contrato).order_by(models.Contrato.id.desc()).all()


@router.post("/", response_model=schemas.ContratoOut)
def crear(data: schemas.ContratoCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = models.Contrato(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.get("/{id}", response_model=schemas.ContratoOut)
def detalle(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = db.query(models.Contrato).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrado")
    return obj


@router.patch("/{id}", response_model=schemas.ContratoOut)
def editar(id: int, data: schemas.ContratoCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = db.query(models.Contrato).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrado")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/{id}")
def eliminar(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = db.query(models.Contrato).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrado")
    db.delete(obj); db.commit()
    return {"ok": True}
