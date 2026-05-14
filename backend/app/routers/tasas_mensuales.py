"""
Actualización mensual de tasas municipales por inmueble.

Flujo: el admin entra una vez al mes, repasa todas las propiedades, carga
los nuevos importes (los puede sacar del portal de la muni o donde sea)
y los guarda en bulk. El valor vigente queda como `tasa_municipal` en la
propiedad. Cuando se genera el pago del mes, se snapshot ahí.

  GET  /api/tasas-mensuales/resumen     dashboard: cuántas propiedades,
                                         cuándo fue la última actualización,
                                         cuántas faltan actualizar este mes.
  POST /api/tasas-mensuales/aplicar     body: [{propiedad_id, monto}, ...]
                                         pisa la tasa_municipal y registra
                                         tasa_consultada_at = ahora.
  GET  /api/tasas-mensuales/historico/{propiedad_id}
                                         muestra qué se cobró mes a mes
                                         (desde la tabla de pagos).
"""
from datetime import datetime, date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.security import get_current_user
from app import models
from app.services.workspace import apply_workspace_filter as _ws


router = APIRouter(prefix="/api/tasas-mensuales", tags=["tasas"])


class ItemActualizar(BaseModel):
    propiedad_id: int
    monto: float


class AplicarIn(BaseModel):
    items: List[ItemActualizar]
    periodo: Optional[str] = None   # "YYYY-MM" — solo para logging/registro


@router.get("/resumen")
def resumen(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Resumen del estado de las actualizaciones de tasas para el mes actual."""
    # Solo nos importan las propiedades en alquiler (no las de venta)
    props = (
        _ws(db.query(models.Propiedad), models.Propiedad, user)
          .filter(models.Propiedad.modalidad != models.PropiedadModalidad.venta)
          .order_by(models.Propiedad.direccion)
          .all()
    )

    hoy = datetime.utcnow()
    mes_inicio = datetime(hoy.year, hoy.month, 1)

    actualizadas_este_mes = 0
    sin_actualizar = []
    for p in props:
        if p.tasa_consultada_at and p.tasa_consultada_at >= mes_inicio:
            actualizadas_este_mes += 1
        else:
            sin_actualizar.append({
                "id": p.id,
                "direccion": p.direccion,
                "ciudad": p.ciudad,
                "tasa_actual": p.tasa_municipal or 0,
                "tasa_consultada_at": (
                    p.tasa_consultada_at.isoformat() if p.tasa_consultada_at else None
                ),
            })

    return {
        "total_propiedades":         len(props),
        "actualizadas_este_mes":     actualizadas_este_mes,
        "pendientes":                len(sin_actualizar),
        "mes_actual":                hoy.strftime("%Y-%m"),
        "primer_pendiente":          sin_actualizar[:5],
    }


@router.get("/lista")
def lista(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Lista todas las propiedades en alquiler con su tasa vigente y fecha
    de última actualización. Es la fuente de datos de la página del frontend."""
    props = (
        _ws(db.query(models.Propiedad), models.Propiedad, user)
          .filter(models.Propiedad.modalidad != models.PropiedadModalidad.venta,
                  models.Propiedad.tokko_id.is_(None) | (models.Propiedad.tokko_id == ""))
          .order_by(models.Propiedad.direccion)
          .all()
    )

    return [
        {
            "id": p.id,
            "direccion":          p.direccion,
            "ciudad":             p.ciudad,
            "tipo":               (p.tipo.value if hasattr(p.tipo, "value") else p.tipo),
            "numero_referencia":  p.numero_referencia,
            "tasa_municipal":     p.tasa_municipal or 0,
            "tasa_consultada_at": (
                p.tasa_consultada_at.isoformat() if p.tasa_consultada_at else None
            ),
            "propietario_nombre": (
                f"{p.propietario.nombre or ''} {p.propietario.apellido or ''}".strip()
                if p.propietario else None
            ),
        }
        for p in props
    ]


@router.post("/aplicar")
def aplicar(
    data: AplicarIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Aplica un listado de actualizaciones de tasa. Bulk.

    No es estrictamente admin-only — cualquier user con rol alquileres o
    admin puede correrlo. Idempotente: si pasás un monto igual al actual,
    actualiza el timestamp pero no genera ruido.
    """
    if not data.items:
        raise HTTPException(400, "Lista vacía")

    actualizados = 0
    no_encontrados = []
    ahora = datetime.utcnow()

    for item in data.items:
        prop = _ws(db.query(models.Propiedad), models.Propiedad, user).filter_by(id=item.propiedad_id).first()
        if not prop:
            no_encontrados.append(item.propiedad_id)
            continue
        # Solo persiste si el monto es positivo (o cero explícito)
        if item.monto is None or item.monto < 0:
            continue
        prop.tasa_municipal = item.monto
        prop.tasa_consultada_at = ahora
        actualizados += 1

    db.commit()

    return {
        "ok": True,
        "actualizados": actualizados,
        "no_encontrados": no_encontrados,
        "periodo": data.periodo or ahora.strftime("%Y-%m"),
        "aplicado_at": ahora.isoformat(),
    }


@router.get("/historico/{propiedad_id}")
def historico(
    propiedad_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Historial de lo que se cobró en concepto de tasa municipal mes a mes
    para esta propiedad (de la tabla de pagos)."""
    prop = _ws(db.query(models.Propiedad), models.Propiedad, user).filter_by(id=propiedad_id).first()
    if not prop:
        raise HTTPException(404, "Propiedad no encontrada")

    # Pagos de todos los contratos asociados a la propiedad
    pagos = (
        _ws(db.query(models.Pago), models.Pago, user)
          .join(models.Contrato, models.Pago.contrato_id == models.Contrato.id)
          .filter(models.Contrato.propiedad_id == propiedad_id)
          .filter(models.Pago.monto_municipal > 0)
          .order_by(models.Pago.fecha_vencimiento.desc())
          .limit(36)
          .all()
    )

    return {
        "propiedad_id": propiedad_id,
        "direccion": prop.direccion,
        "tasa_actual": prop.tasa_municipal or 0,
        "ultima_actualizacion": (
            prop.tasa_consultada_at.isoformat() if prop.tasa_consultada_at else None
        ),
        "historico": [
            {
                "periodo":          p.periodo,
                "fecha_vencimiento": p.fecha_vencimiento.isoformat() if p.fecha_vencimiento else None,
                "monto_municipal":   p.monto_municipal or 0,
                "estado":            p.estado.value if hasattr(p.estado, "value") else p.estado,
            }
            for p in pagos
        ],
    }
