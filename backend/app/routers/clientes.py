from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.security import get_current_user
from app import models, schemas
from app.services.workspace import apply_workspace_filter, workspace_flag

router = APIRouter(prefix="/api/clientes", tags=["clientes"])


def _scope(db: Session, user):
    return apply_workspace_filter(db.query(models.Cliente), models.Cliente, user)


@router.get("/", response_model=List[schemas.ClienteOut])
def listar(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _scope(db, user).order_by(models.Cliente.id.desc()).all()


@router.post("/", response_model=schemas.ClienteOut)
def crear(data: schemas.ClienteCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = models.Cliente(**data.model_dump())
    obj.is_demo = workspace_flag(user)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.patch("/{id}", response_model=schemas.ClienteOut)
def editar(id: int, data: schemas.ClienteCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = _scope(db, user).filter_by(id=id).first()
    if not obj: raise HTTPException(404, "No encontrado")
    for k, v in data.model_dump(exclude_unset=True).items():
        if k == "is_demo":
            continue
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/{id}")
def eliminar(
    id: int,
    forzar: bool = False,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Elimina cliente. Si tiene contratos o propiedades vinculadas, bloquea
    con un mensaje claro a menos que se pase ?forzar=true (cascada manual).

    Cascada: si forzar=true,
      - si es propietario → desvincula sus propiedades (propietario_id = NULL)
      - si es inquilino → bloquea siempre (no se eliminan contratos)
    """
    obj = _scope(db, user).filter_by(id=id).first()
    if not obj:
        raise HTTPException(404, "Cliente no encontrado")

    # Verificar contratos donde figura como inquilino (FK)
    contratos = (
        db.query(models.Contrato)
          .filter(models.Contrato.inquilino_id == id)
          .count()
    )
    if contratos > 0:
        raise HTTPException(
            409,
            f"No se puede eliminar: este cliente figura como inquilino en "
            f"{contratos} contrato{'s' if contratos != 1 else ''}. "
            f"Eliminá o reasigná esos contratos primero.",
        )

    # Si es propietario y tiene propiedades, decidir según `forzar`
    if obj.rol == models.ClienteRol.propietario:
        props = db.query(models.Propiedad).filter_by(propietario_id=id).all()
        if props and not forzar:
            raise HTTPException(
                409,
                f"Este propietario tiene {len(props)} propiedad"
                f"{'es' if len(props) != 1 else ''} asignada"
                f"{'s' if len(props) != 1 else ''}. "
                f"Pasá ?forzar=true para desvincularlas y eliminar, "
                f"o reasigná las propiedades primero.",
            )
        # Desvincular propiedades
        for p in props:
            p.propietario_id = None
        db.flush()

    db.delete(obj)
    db.commit()
    return {"ok": True}


@router.get("/{id}/historial-alquiler")
def historial_alquiler(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Devuelve todos los contratos donde el cliente figura como inquilino
    junto con el status actual (alquilando o no).

    Útil para la vista de Clientes en el área de alquileres."""
    c = _scope(db, user).filter_by(id=id).first()
    if not c:
        raise HTTPException(404, "Cliente no encontrado")

    contratos = (
        apply_workspace_filter(db.query(models.Contrato), models.Contrato, user)
          .filter(models.Contrato.inquilino_id == id)
          .order_by(models.Contrato.fecha_inicio.desc().nullslast())
          .all()
    )

    hoy = date.today()
    items = []
    for k in contratos:
        prop = k.propiedad
        items.append({
            "contrato_id": k.id,
            "tipo": k.tipo.value if hasattr(k.tipo, "value") else k.tipo,
            "estado": k.estado.value if hasattr(k.estado, "value") else k.estado,
            "fecha_inicio": k.fecha_inicio.isoformat() if k.fecha_inicio else None,
            "fecha_fin": k.fecha_fin.isoformat() if k.fecha_fin else None,
            "propiedad": {
                "id": prop.id if prop else None,
                "direccion": prop.direccion if prop else None,
                "ciudad": prop.ciudad if prop else None,
            } if prop else None,
            "monto_inicial": k.monto_inicial,
            "vigente_hoy": bool(
                k.fecha_inicio and k.fecha_fin
                and k.fecha_inicio <= hoy <= k.fecha_fin
                and (k.estado.value if hasattr(k.estado, "value") else k.estado) == "vigente"
            ),
        })

    alquilando = any(it["vigente_hoy"] for it in items)

    return {
        "cliente_id": c.id,
        "nombre": f"{c.nombre or ''} {c.apellido or ''}".strip(),
        "cliente_desde": c.created_at.isoformat() if c.created_at else None,
        "alquilando": alquilando,
        "contratos_total": len(items),
        "contratos": items,
    }
