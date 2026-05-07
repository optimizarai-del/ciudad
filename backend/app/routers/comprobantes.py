import base64
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models
from app.services.email_service import enviar_email, smtp_configurado

router = APIRouter(prefix="/api/comprobantes", tags=["comprobantes"])


def _serialize(c: models.Comprobante) -> dict:
    return {
        "id": c.id,
        "pago_id": c.pago_id,
        "tipo": c.tipo.value if hasattr(c.tipo, "value") else c.tipo,
        "destinatario_nombre": c.destinatario_nombre,
        "destinatario_email": c.destinatario_email,
        "monto_total": c.monto_total,
        "monto_comision": c.monto_comision,
        "monto_neto": c.monto_neto,
        "enviado_email": c.enviado_email,
        "fecha_envio": c.fecha_envio.isoformat() if c.fecha_envio else None,
        "error_envio": c.error_envio,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/")
def listar(
    pago_id: Optional[int] = None,
    contrato_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    q = db.query(models.Comprobante).order_by(models.Comprobante.id.desc())
    if pago_id:
        q = q.filter(models.Comprobante.pago_id == pago_id)
    if contrato_id:
        pago_ids = [p.id for p in db.query(models.Pago.id).filter(models.Pago.contrato_id == contrato_id).all()]
        q = q.filter(models.Comprobante.pago_id.in_(pago_ids or [-1]))
    return [_serialize(c) for c in q.all()]


@router.get("/{id}/pdf")
def descargar(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = db.query(models.Comprobante).filter_by(id=id).first()
    if not c:
        raise HTTPException(404, "Comprobante no encontrado")
    if not c.pdf_blob:
        raise HTTPException(404, "PDF no disponible para este comprobante")
    pdf = base64.b64decode(c.pdf_blob)
    fname = f"{c.tipo.value if hasattr(c.tipo,'value') else c.tipo}-{c.id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{fname}"'},
    )


@router.post("/{id}/reenviar")
def reenviar(id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = db.query(models.Comprobante).filter_by(id=id).first()
    if not c:
        raise HTTPException(404, "Comprobante no encontrado")
    if not c.destinatario_email:
        raise HTTPException(400, "El comprobante no tiene email destinatario")
    if not smtp_configurado():
        raise HTTPException(400, "SMTP no configurado en el servidor")

    pdf = base64.b64decode(c.pdf_blob) if c.pdf_blob else None
    asunto = "Liquidación CIUDAD." if c.tipo == models.ComprobanteTipo.propietario else "Recibo de pago CIUDAD."
    cuerpo = f"Estimado/a {c.destinatario_nombre or ''},\n\nAdjuntamos el comprobante solicitado.\n\nCIUDAD."
    ok, msg = enviar_email(c.destinatario_email, asunto, cuerpo, pdf, f"comprobante-{c.id}.pdf")
    from datetime import datetime
    c.enviado_email = ok
    c.fecha_envio = datetime.utcnow() if ok else c.fecha_envio
    c.error_envio = None if ok else msg
    db.commit()
    return {"ok": ok, "mensaje": msg}
