from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.security import get_current_user
from app import models, schemas
from app.services.indices_service import (
    get_tasas_mensuales,
    IPC_MENSUAL_FALLBACK,
    ICL_MENSUAL_FALLBACK,
)

router = APIRouter(prefix="/api/calculadora", tags=["calculadora"])


def _factor_ajuste(
    indice: str,
    periodicidad: int,
    meses_transcurridos: int,
    porc_fijo: float,
    ipc_mensual: float,
    icl_mensual: float,
) -> float:
    """Factor multiplicador acumulado según periodos cumplidos."""
    if indice == "sin_ajuste" or meses_transcurridos < periodicidad:
        return 1.0
    periodos = meses_transcurridos // periodicidad
    if indice == "fijo":
        tasa_periodo = (porc_fijo or 0) / 100.0
    elif indice == "icl":
        tasa_periodo = (1 + icl_mensual) ** periodicidad - 1
    else:  # ipc por default
        tasa_periodo = (1 + ipc_mensual) ** periodicidad - 1
    return (1 + tasa_periodo) ** periodos


@router.post("/", response_model=schemas.CalculoOut)
async def calcular(data: schemas.CalculoIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # 1. Resolver propiedad
    prop = None
    if data.propiedad_id:
        prop = db.query(models.Propiedad).filter_by(id=data.propiedad_id).first()
    elif data.direccion:
        prop = (
            db.query(models.Propiedad)
            .filter(models.Propiedad.direccion.ilike(f"%{data.direccion}%"))
            .first()
        )
    if not prop:
        raise HTTPException(404, "Propiedad no encontrada por dirección o id")

    # 2. Buscar contrato vigente
    contrato = (
        db.query(models.Contrato)
        .filter(models.Contrato.propiedad_id == prop.id)
        .filter(or_(models.Contrato.estado == "vigente", models.Contrato.estado == "borrador"))
        .order_by(models.Contrato.id.desc())
        .first()
    )

    # 3. Cargar tasas reales desde INDEC/BCRA (con cache)
    tasas = await get_tasas_mensuales()
    ipc_mensual = tasas["ipc_mensual"]
    icl_mensual = tasas["icl_mensual"]

    base_alquiler = float(prop.precio_alquiler or 0)
    factor = 1.0
    indice_aplicado = "sin_ajuste"
    periodos_aplicados = 0

    if contrato:
        base_alquiler = float(contrato.monto_inicial or prop.precio_alquiler or 0)
        fecha_obj = data.fecha or date.today()
        if contrato.fecha_inicio and fecha_obj > contrato.fecha_inicio:
            meses = (fecha_obj.year - contrato.fecha_inicio.year) * 12 + (fecha_obj.month - contrato.fecha_inicio.month)
            indice_aplicado = contrato.indice_ajuste.value if hasattr(contrato.indice_ajuste, "value") else contrato.indice_ajuste
            factor = _factor_ajuste(
                indice_aplicado,
                contrato.periodicidad_meses or 3,
                meses,
                contrato.porcentaje_fijo or 0,
                ipc_mensual,
                icl_mensual,
            )
            periodos_aplicados = meses // (contrato.periodicidad_meses or 3)

    alquiler_act = round(base_alquiler * factor, 2)
    expensas = float(prop.expensas or 0)
    # tasas_municipales agrupa lo que antes era impuesto_inmobiliario + tasa_municipal
    tasas_municipales = float(prop.tasa_municipal or 0) + float(prop.impuesto_inmobiliario or 0)
    total = round(alquiler_act + expensas + tasas_municipales, 2)

    # Nota dinámica según fuente real / fallback
    if indice_aplicado == "ipc":
        usa_real = tasas.get("ipc_ok", False)
        nota = (
            f"IPC mensual {round(ipc_mensual*100,2)}% (fuente {tasas.get('ipc_fuente')}). "
            + (f"Período {tasas.get('ipc_periodo')}." if tasas.get("ipc_periodo") else "")
        )
    elif indice_aplicado == "icl":
        usa_real = tasas.get("icl_ok", False)
        nota = (
            f"ICL mensual {round(icl_mensual*100,2)}% (fuente {tasas.get('icl_fuente')}). "
            + (f"Última fecha {tasas.get('icl_fecha')}." if tasas.get("icl_fecha") else "")
        )
    else:
        usa_real = False
        nota = "Cálculo sin ajuste o con porcentaje fijo del contrato."

    return {
        "propiedad": {
            "id": prop.id, "codigo": prop.codigo, "direccion": prop.direccion,
            "tipo": prop.tipo.value if hasattr(prop.tipo, "value") else prop.tipo,
        },
        "contrato": (
            {
                "id": contrato.id, "codigo": contrato.codigo,
                "indice": indice_aplicado, "periodicidad_meses": contrato.periodicidad_meses,
                "fecha_inicio": str(contrato.fecha_inicio) if contrato.fecha_inicio else None,
            } if contrato else None
        ),
        "base_alquiler": base_alquiler,
        "factor_ajuste": round(factor, 4),
        "alquiler_actualizado": alquiler_act,
        "expensas": expensas,
        # mantenemos los nombres legacy (todo en tasa_municipal, inmobiliario en 0)
        "impuesto_inmobiliario": 0,
        "tasa_municipal": tasas_municipales,
        "tasas_municipales": tasas_municipales,
        "total_mensual": total,
        "detalle": {
            "indice": indice_aplicado,
            "periodos_aplicados": periodos_aplicados,
            "fecha_calculo": str(data.fecha or date.today()),
            "indice_real": usa_real,
            "ipc_mensual_pct": round(ipc_mensual * 100, 2),
            "icl_mensual_pct": round(icl_mensual * 100, 2),
            "ipc_fuente": tasas.get("ipc_fuente"),
            "icl_fuente": tasas.get("icl_fuente"),
            "nota": nota,
        },
    }
