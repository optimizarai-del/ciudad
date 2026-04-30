from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models

router = APIRouter(tags=["pagos"])


class PagoCreate(BaseModel):
    periodo: Optional[str] = None
    fecha_vencimiento: Optional[date] = None
    fecha_pago: Optional[date] = None
    monto_alquiler: Optional[float] = 0
    monto_expensas: Optional[float] = 0
    monto_impuestos: Optional[float] = 0
    monto_municipal: Optional[float] = 0
    monto_otros: Optional[float] = 0
    monto_total: Optional[float] = 0
    estado: Optional[str] = "pendiente"
    notas: Optional[str] = None


class PagoOut(BaseModel):
    id: int
    contrato_id: int
    periodo: Optional[str]
    fecha_vencimiento: Optional[date]
    fecha_pago: Optional[date]
    monto_alquiler: float
    monto_expensas: float
    monto_impuestos: float
    monto_municipal: float
    monto_otros: float
    monto_total: float
    estado: str
    notas: Optional[str]

    class Config:
        from_attributes = True


@router.get("/api/contratos/{contrato_id}/pagos", response_model=List[PagoOut])
def listar_pagos(contrato_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    contrato = db.query(models.Contrato).filter_by(id=contrato_id).first()
    if not contrato:
        raise HTTPException(404, "Contrato no encontrado")
    return db.query(models.Pago).filter_by(contrato_id=contrato_id).order_by(models.Pago.fecha_vencimiento).all()


@router.post("/api/contratos/{contrato_id}/pagos", response_model=PagoOut)
def crear_pago(contrato_id: int, data: PagoCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    contrato = db.query(models.Contrato).filter_by(id=contrato_id).first()
    if not contrato:
        raise HTTPException(404, "Contrato no encontrado")

    total = data.monto_total or (
        (data.monto_alquiler or 0)
        + (data.monto_expensas or 0)
        + (data.monto_impuestos or 0)
        + (data.monto_municipal or 0)
        + (data.monto_otros or 0)
    )

    pago = models.Pago(
        contrato_id=contrato_id,
        periodo=data.periodo,
        fecha_vencimiento=data.fecha_vencimiento,
        fecha_pago=data.fecha_pago,
        monto_alquiler=data.monto_alquiler or 0,
        monto_expensas=data.monto_expensas or 0,
        monto_impuestos=data.monto_impuestos or 0,
        monto_municipal=data.monto_municipal or 0,
        monto_otros=data.monto_otros or 0,
        monto_total=total,
        estado=data.estado or "pendiente",
        notas=data.notas,
    )
    db.add(pago)
    db.commit()
    db.refresh(pago)
    return pago


@router.patch("/api/pagos/{pago_id}", response_model=PagoOut)
def actualizar_pago(pago_id: int, data: PagoCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    pago = db.query(models.Pago).filter_by(id=pago_id).first()
    if not pago:
        raise HTTPException(404, "Pago no encontrado")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(pago, k, v)
    db.commit()
    db.refresh(pago)
    return pago


@router.delete("/api/pagos/{pago_id}")
def eliminar_pago(pago_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    pago = db.query(models.Pago).filter_by(id=pago_id).first()
    if not pago:
        raise HTTPException(404, "Pago no encontrado")
    db.delete(pago)
    db.commit()
    return {"ok": True}
