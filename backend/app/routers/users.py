"""
Gestión de usuarios del equipo CIUDAD.

  GET    /api/users           — lista (cualquier user autenticado)
  POST   /api/users           — crear (admin) + email de bienvenida
  PATCH  /api/users/{id}      — editar rol/nombre/telefono/is_active (admin)
  DELETE /api/users/{id}      — eliminar (admin) — hard delete con guards
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.security import get_current_user, hash_pw
from app import models, schemas
from app.services import welcome_email

router = APIRouter(prefix="/api/users", tags=["users"])


def _require_admin(user):
    if user.role != models.UserRole.admin:
        raise HTTPException(403, "Solo admins pueden gestionar usuarios")


class UserCreateIn(BaseModel):
    nombre: str
    email: EmailStr
    password: str
    telefono: Optional[str] = None
    role: str = "alquileres"
    enviar_email: bool = True


class UserCreateOut(BaseModel):
    user: schemas.UserOut
    email_enviado: bool
    email_motivo: Optional[str] = None


class UserUpdate(BaseModel):
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/", response_model=List[schemas.UserOut])
def listar(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(models.User).order_by(models.User.id).all()


@router.post("/", response_model=UserCreateOut, status_code=201)
def crear(data: UserCreateIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Crea un usuario nuevo y envía email de bienvenida con credenciales.

    Solo admin. Si SMTP no está configurado, el usuario se crea igual y
    el campo `email_enviado` viene en false con el motivo en `email_motivo`.
    """
    _require_admin(user)

    if len(data.password) < 6:
        raise HTTPException(400, "La contraseña debe tener al menos 6 caracteres")

    email_norm = data.email.strip().lower()
    if db.query(models.User).filter_by(email=email_norm).first():
        raise HTTPException(400, "Ya existe un usuario con ese email")

    try:
        rol_enum = models.UserRole(data.role)
    except ValueError:
        raise HTTPException(400, f"Rol inválido: {data.role}")

    nuevo = models.User(
        nombre=data.nombre.strip(),
        email=email_norm,
        telefono=data.telefono or None,
        password_hash=hash_pw(data.password),
        role=rol_enum,
        is_active=True,
    )
    db.add(nuevo); db.commit(); db.refresh(nuevo)

    # Welcome email — no bloquea la creación si falla
    ok, motivo = (False, "Envío deshabilitado")
    if data.enviar_email:
        ok, motivo = welcome_email.enviar_welcome(
            nombre=nuevo.nombre,
            email=nuevo.email,
            password=data.password,   # texto plano sólo para el mail; no se guarda
            role=data.role,
        )

    return UserCreateOut(user=nuevo, email_enviado=ok, email_motivo=motivo)


@router.patch("/{id}", response_model=schemas.UserOut)
def editar(id: int, data: UserUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _require_admin(user)
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


@router.delete("/{id}", status_code=204)
def eliminar(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Hard delete del usuario.

    Guards:
      - Solo admin.
      - No se puede borrar a sí mismo (evita lockout accidental).
      - No se puede borrar el último admin del sistema.
    FKs débiles a `eventos.user_id` y `consultas_ia.user_id` se ponen en NULL
    antes del delete para que no falle por restrict.
    """
    _require_admin(user)

    if id == user.id:
        raise HTTPException(400, "No podés eliminar tu propio usuario")

    obj = db.query(models.User).filter_by(id=id).first()
    if not obj:
        raise HTTPException(404, "Usuario no encontrado")

    if obj.role == models.UserRole.admin:
        otros_admins = (
            db.query(models.User)
              .filter(models.User.role == models.UserRole.admin,
                      models.User.id != id,
                      models.User.is_active.is_(True))
              .count()
        )
        if otros_admins == 0:
            raise HTTPException(
                400,
                "No podés eliminar el último administrador del sistema",
            )

    # Limpiar FKs débiles antes del delete (los registros se mantienen sin owner)
    db.execute(text("UPDATE eventos SET user_id = NULL WHERE user_id = :id"),
               {"id": id})
    db.execute(text("UPDATE consultas_ia SET user_id = NULL WHERE user_id = :id"),
               {"id": id})
    db.delete(obj)
    db.commit()
    return None
