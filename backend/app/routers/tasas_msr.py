"""
Endpoints para consultar tasa/deuda de la Municipalidad de Santa Rosa.

  GET  /api/tasas-msr/config                       devuelve sitekey de
                                                    reCAPTCHA para que el
                                                    frontend monte el widget
  POST /api/propiedades/{id}/consultar-tasa-msr    recibe captcha_token
                                                    del frontend, consulta
                                                    el portal y guarda
                                                    la última tasa
"""
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models
from app.services import msr_consulta


router = APIRouter(prefix="/api", tags=["tasas-msr"])


@router.get("/tasas-msr/config")
def config(user=Depends(get_current_user)):
    """Devuelve la configuración necesaria para el widget de reCAPTCHA."""
    sk = msr_consulta.sitekey()
    return {
        "habilitado": bool(sk),
        "sitekey":    sk,
        "portal_url": "https://consultadeuda.santarosa.gob.ar/",
    }


class ConsultaIn(BaseModel):
    captcha_token: str
    action: Optional[str] = "getCuenta"
    ofic99: Optional[str] = "1"


@router.post("/propiedades/{prop_id}/consultar-tasa-msr")
async def consultar(
    prop_id: int,
    data: ConsultaIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Consulta la deuda actual de la propiedad en la Municipalidad de
    Santa Rosa. Requiere que la propiedad tenga `numero_referencia` cargado
    y que el frontend mande el token de reCAPTCHA resuelto."""
    prop = db.query(models.Propiedad).filter_by(id=prop_id).first()
    if not prop:
        raise HTTPException(404, "Propiedad no encontrada")
    if not prop.numero_referencia:
        raise HTTPException(400, "Esta propiedad no tiene número de referencia municipal. Cargalo primero.")

    resultado = await msr_consulta.consultar_deuda(
        padron=prop.numero_referencia,
        captcha_token=data.captcha_token,
        action=data.action or "getCuenta",
        ofic99=data.ofic99 or "1",
    )

    if not resultado.get("ok"):
        raise HTTPException(502, resultado.get("error") or "Error consultando la municipalidad")

    # Guardar última consulta en la propiedad (para el botón "Ver deuda")
    prop.tasa_consultada_at = datetime.utcnow()
    prop.tasa_detalle = json.dumps({
        "cuotas":   resultado["cuotas"],
        "total":    resultado["total"],
        "cantidad": resultado["cantidad"],
        "consultado_at": prop.tasa_consultada_at.isoformat(),
    }, default=str, ensure_ascii=False)

    # Si hay cuotas, usar la más reciente como tasa mensual de referencia
    if resultado["cuotas"]:
        # Tomar el importe del primer item (suele ser el más actual)
        # o la mediana si hay variación.
        importes = [c["importe"] for c in resultado["cuotas"] if c["importe"] > 0]
        if importes:
            prop.tasa_municipal = importes[0]

    db.commit()
    db.refresh(prop)

    return {
        "ok": True,
        "propiedad_id": prop.id,
        "total":     resultado["total"],
        "cantidad":  resultado["cantidad"],
        "cuotas":    resultado["cuotas"],
        "consultado_at": prop.tasa_consultada_at.isoformat(),
        "tasa_municipal": prop.tasa_municipal,
    }


@router.get("/propiedades/{prop_id}/tasa-msr-cache")
def cache(
    prop_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Devuelve el último resultado guardado de la consulta a la
    municipalidad (sin volver a consultar). Útil para mostrar 'Ver deuda'
    sin gastar un captcha más."""
    prop = db.query(models.Propiedad).filter_by(id=prop_id).first()
    if not prop:
        raise HTTPException(404, "Propiedad no encontrada")
    if not prop.tasa_detalle:
        return {"disponible": False, "mensaje": "No hay consulta previa"}
    try:
        detalle = json.loads(prop.tasa_detalle)
    except Exception:
        return {"disponible": False, "mensaje": "Caché inválida"}
    return {
        "disponible": True,
        "consultado_at": prop.tasa_consultada_at.isoformat() if prop.tasa_consultada_at else None,
        "detalle": detalle,
        "tasa_municipal_actual": prop.tasa_municipal,
        "numero_referencia": prop.numero_referencia,
    }
