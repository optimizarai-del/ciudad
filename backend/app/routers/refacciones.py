"""
Refacciones / arreglos en propiedades.

Flujo principal:
- Cargás una refacción cuando se hace un arreglo. Especificás quién la paga
  (inquilino o propietario) y el monto.
- Si la paga el inquilino: queda `pendiente` y al registrar el próximo pago
  del alquiler de ese contrato, se descuenta automáticamente del total.
  La refacción pasa a estado=`aplicada` y queda vinculada al pago.
- Si la paga el propietario: queda como gasto a debitarle en la próxima
  liquidación (se ve en el módulo de liquidaciones).
"""
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models, schemas
from app.services.workspace import apply_workspace_filter, workspace_flag


router = APIRouter(prefix="/api/refacciones", tags=["refacciones"])


def _scope(db: Session, user):
    return apply_workspace_filter(db.query(models.Refaccion), models.Refaccion, user)


def _to_out(r: models.Refaccion) -> dict:
    """Serializa una refacción agregando datos relacionados que el frontend
    usa para mostrar la lista sin tener que hacer joins en el cliente."""
    return {
        "id": r.id,
        "propiedad_id": r.propiedad_id,
        "contrato_id": r.contrato_id,
        "fecha": r.fecha,
        "descripcion": r.descripcion,
        "monto": r.monto,
        "pagador": r.pagador.value if hasattr(r.pagador, "value") else r.pagador,
        "estado": r.estado.value if hasattr(r.estado, "value") else r.estado,
        "pago_id": r.pago_id,
        "notas": r.notas,
        "propiedad_direccion": r.propiedad.direccion if r.propiedad else None,
        "contrato_codigo": (r.contrato.codigo if r.contrato else None),
        "created_at": r.created_at,
    }


@router.get("")
def listar(
    propiedad_id: Optional[int] = None,
    contrato_id: Optional[int] = None,
    estado: Optional[str] = None,
    pagador: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    q = _scope(db, user)
    if propiedad_id:
        q = q.filter(models.Refaccion.propiedad_id == propiedad_id)
    if contrato_id:
        q = q.filter(models.Refaccion.contrato_id == contrato_id)
    if estado:
        q = q.filter(models.Refaccion.estado == estado)
    if pagador:
        q = q.filter(models.Refaccion.pagador == pagador)
    items = q.order_by(models.Refaccion.fecha.desc(), models.Refaccion.id.desc()).all()
    return [_to_out(r) for r in items]


@router.get("/resumen")
def resumen(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """KPIs para el dashboard del módulo."""
    total_pend_inq = _scope(db, user).filter(
        models.Refaccion.estado == models.RefaccionEstado.pendiente,
        models.Refaccion.pagador == models.RefaccionPagador.inquilino,
    ).all()
    total_pend_prop = _scope(db, user).filter(
        models.Refaccion.estado == models.RefaccionEstado.pendiente,
        models.Refaccion.pagador == models.RefaccionPagador.propietario,
    ).all()
    return {
        "pendientes_inquilino": {
            "cantidad": len(total_pend_inq),
            "monto": sum((r.monto or 0) for r in total_pend_inq),
        },
        "pendientes_propietario": {
            "cantidad": len(total_pend_prop),
            "monto": sum((r.monto or 0) for r in total_pend_prop),
        },
    }


@router.post("", response_model=schemas.RefaccionOut)
def crear(data: schemas.RefaccionCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # Validar propiedad (en el workspace del usuario)
    from app.services.workspace import apply_workspace_filter as _aw
    prop = _aw(db.query(models.Propiedad), models.Propiedad, user).filter_by(id=data.propiedad_id).first()
    if not prop:
        raise HTTPException(404, "Propiedad no encontrada")

    # Si no se mandó contrato, intentamos linkearlo al contrato vigente de
    # la propiedad — útil para descontar después en el próximo pago.
    contrato_id = data.contrato_id
    if not contrato_id:
        c = (
            _aw(db.query(models.Contrato), models.Contrato, user)
            .filter(
                models.Contrato.propiedad_id == data.propiedad_id,
                models.Contrato.estado == models.ContratoEstado.vigente,
            )
            .first()
        )
        contrato_id = c.id if c else None

    obj = models.Refaccion(
        propiedad_id=data.propiedad_id,
        contrato_id=contrato_id,
        fecha=data.fecha or date.today(),
        descripcion=data.descripcion.strip(),
        monto=float(data.monto or 0),
        pagador=models.RefaccionPagador(data.pagador or "inquilino"),
        estado=models.RefaccionEstado(data.estado or "pendiente"),
        notas=data.notas,
        is_demo=workspace_flag(user),
    )
    db.add(obj); db.commit(); db.refresh(obj)
    return _to_out(obj)


@router.patch("/{id}", response_model=schemas.RefaccionOut)
def editar(id: int, data: schemas.RefaccionCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = _scope(db, user).filter_by(id=id).first()
    if not obj:
        raise HTTPException(404, "Refacción no encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        if k == "pagador" and v is not None:
            setattr(obj, k, models.RefaccionPagador(v))
        elif k == "estado" and v is not None:
            setattr(obj, k, models.RefaccionEstado(v))
        else:
            setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return _to_out(obj)


@router.delete("/{id}")
def eliminar(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = _scope(db, user).filter_by(id=id).first()
    if not obj:
        raise HTTPException(404, "Refacción no encontrada")
    if obj.estado == models.RefaccionEstado.aplicada:
        raise HTTPException(400, "No se puede eliminar una refacción ya aplicada a un pago. Cancelala primero.")
    db.delete(obj); db.commit()
    return {"ok": True}
