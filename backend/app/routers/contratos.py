from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.security import get_current_user
from app import models, schemas
from app.services.pdf_service import generar_pdf_contrato

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


def _cliente_dict(c: models.Cliente | None) -> dict:
    if not c:
        return {"nombre_completo": "Sin asignar", "documento": None, "email": None, "telefono": None}
    nombre = " ".join([p for p in [c.nombre, c.apellido] if p])
    if c.razon_social:
        nombre = c.razon_social
    return {
        "nombre_completo": nombre or "Sin asignar",
        "documento": c.documento,
        "email": c.email,
        "telefono": c.telefono,
    }


def _propiedad_dict(p: models.Propiedad | None) -> dict:
    if not p:
        return {"direccion": "—", "ciudad": "—", "provincia": None, "tipo": "—"}
    return {
        "direccion": p.direccion,
        "ciudad": p.ciudad,
        "provincia": p.provincia,
        "tipo": (p.tipo.value if hasattr(p.tipo, "value") else str(p.tipo or "")).replace("_", " "),
    }


@router.get("/{id}/pdf")
def pdf_contrato(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Genera el PDF legal del contrato según su tipo."""
    contrato = db.query(models.Contrato).filter_by(id=id).first()
    if not contrato:
        raise HTTPException(404, "Contrato no encontrado")

    propiedad = db.query(models.Propiedad).filter_by(id=contrato.propiedad_id).first()
    locatario = db.query(models.Cliente).filter_by(id=contrato.inquilino_id).first() if contrato.inquilino_id else None

    locador = None
    if propiedad and propiedad.propietario_id:
        locador = db.query(models.Cliente).filter_by(id=propiedad.propietario_id).first()

    ctx = {
        "contrato": {
            "id": contrato.id,
            "codigo": contrato.codigo,
            "tipo": contrato.tipo.value if hasattr(contrato.tipo, "value") else contrato.tipo,
            "estado": contrato.estado.value if hasattr(contrato.estado, "value") else contrato.estado,
            "fecha_inicio": contrato.fecha_inicio,
            "fecha_fin": contrato.fecha_fin,
            "monto_inicial": contrato.monto_inicial,
            "deposito": contrato.deposito,
            "indice_ajuste": contrato.indice_ajuste.value if hasattr(contrato.indice_ajuste, "value") else contrato.indice_ajuste,
            "periodicidad_meses": contrato.periodicidad_meses,
            "porcentaje_fijo": contrato.porcentaje_fijo,
            "comision_porc": contrato.comision_porc,
            "notas": contrato.notas,
        },
        "propiedad": _propiedad_dict(propiedad),
        "locador": _cliente_dict(locador),
        "locatario": _cliente_dict(locatario),
    }

    pdf = generar_pdf_contrato(ctx)
    filename = f"contrato-{contrato.codigo or contrato.id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
