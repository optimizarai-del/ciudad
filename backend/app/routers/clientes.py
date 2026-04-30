from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.security import get_current_user
from app import models, schemas

router = APIRouter(prefix="/api/clientes", tags=["clientes"])


@router.get("/", response_model=List[schemas.ClienteOut])
def listar(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(models.Cliente).order_by(models.Cliente.id.desc()).all()


@router.post("/", response_model=schemas.ClienteOut)
def crear(data: schemas.ClienteCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = models.Cliente(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.patch("/{id}", response_model=schemas.ClienteOut)
def editar(id: int, data: schemas.ClienteCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = db.query(models.Cliente).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrado")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/{id}")
def eliminar(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = db.query(models.Cliente).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrado")
    db.delete(obj); db.commit()
    return {"ok": True}
