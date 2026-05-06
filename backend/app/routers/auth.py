from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.security import hash_pw, verify_pw, create_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.TokenOut)
def register(data: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter_by(email=data.email).first():
        raise HTTPException(400, "Email ya registrado")
    is_first = db.query(models.User).count() == 0
    user = models.User(
        nombre=data.nombre,
        email=data.email,
        telefono=data.telefono,
        password_hash=hash_pw(data.password),
        role=models.UserRole.admin if is_first else models.UserRole(data.role or "alquileres"),
    )
    db.add(user); db.commit(); db.refresh(user)
    token = create_token({"sub": str(user.id)})
    return {"access_token": token, "user": user}


@router.post("/login", response_model=schemas.TokenOut)
def login(data: schemas.LoginIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(email=data.email).first()
    if not user or not verify_pw(data.password, user.password_hash):
        raise HTTPException(401, "Credenciales inválidas")
    token = create_token({"sub": str(user.id)})
    return {"access_token": token, "user": user}


@router.get("/me", response_model=schemas.UserOut)
def me(user=Depends(get_current_user)):
    return user
