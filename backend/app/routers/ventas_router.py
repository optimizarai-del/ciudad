"""
GET /api/ventas/dashboard  → métricas del área ventas
GET /api/ventas/propiedades → propiedades en venta (propia DB)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models

router = APIRouter(prefix="/api/ventas", tags=["ventas"])

@router.get("/dashboard")
def dashboard_ventas(db: Session = Depends(get_db)):
    propiedades_venta = db.query(models.Propiedad).filter(
        models.Propiedad.modalidad.in_([
            models.PropiedadModalidad.venta,
            models.PropiedadModalidad.ambas
        ])
    ).all()

    disponibles = [p for p in propiedades_venta if p.estado == models.PropiedadEstado.disponible]
    reservadas = [p for p in propiedades_venta if p.estado == models.PropiedadEstado.reservada]

    contratos_venta = db.query(models.Contrato).filter(
        models.Contrato.tipo == models.ContratoTipo.boleto_compraventa
    ).all()
    cerradas = [c for c in contratos_venta if c.estado == models.ContratoEstado.cerrado]

    return {
        "total_en_venta": len(propiedades_venta),
        "disponibles": len(disponibles),
        "reservadas": len(reservadas),
        "vendidas_total": len(cerradas),
        "precio_promedio_usd": round(
            sum(p.precio_venta for p in disponibles if p.precio_venta) / len(disponibles)
            if disponibles else 0, 0
        ),
        "propiedades_destacadas": [
            {
                "id": p.id,
                "direccion": p.direccion,
                "ciudad": p.ciudad,
                "tipo": p.tipo.value if p.tipo else "",
                "precio_venta": p.precio_venta,
                "superficie_m2": p.superficie_m2,
                "ambientes": p.ambientes,
                "estado": p.estado.value if p.estado else "",
            }
            for p in disponibles[:5]
        ]
    }

@router.get("/propiedades")
def propiedades_venta(db: Session = Depends(get_db)):
    props = db.query(models.Propiedad).filter(
        models.Propiedad.modalidad.in_([
            models.PropiedadModalidad.venta,
            models.PropiedadModalidad.ambas
        ])
    ).order_by(models.Propiedad.created_at.desc()).all()

    return [
        {
            "id": p.id,
            "codigo": p.codigo,
            "direccion": p.direccion,
            "ciudad": p.ciudad,
            "tipo": p.tipo.value if p.tipo else "",
            "estado": p.estado.value if p.estado else "",
            "modalidad": p.modalidad.value if p.modalidad else "",
            "precio_venta": p.precio_venta,
            "superficie_m2": p.superficie_m2,
            "ambientes": p.ambientes,
            "descripcion": p.descripcion,
            "tokko_id": p.tokko_id,
        }
        for p in props
    ]
