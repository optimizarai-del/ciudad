from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.security import get_current_user, hash_pw
from app import models, schemas

router = APIRouter(prefix="/api/users", tags=["users"])


class UserUpdate(BaseModel):
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/", response_model=List[schemas.UserOut])
def listar(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(models.User).order_by(models.User.id).all()


@router.patch("/{id}", response_model=schemas.UserOut)
def editar(id: int, data: UserUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user.role != models.UserRole.admin:
        raise HTTPException(403, "Solo admins pueden editar usuarios")
    obj = db.query(models.User).filter_by(id=id).first()
    if not obj:
        raise HTTPException(404, "Usuario no encontrado")
    for k, v in data.model_dump(exclude_unset=True).items():
        if k == "role":
            setattr(obj, k, models.UserRole(v))
        else:
            setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj
