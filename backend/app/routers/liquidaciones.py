"""
Liquidaciones masivas mensuales a propietarios.

  GET  /api/liquidaciones/preview?mes=YYYY-MM   — calcula sin generar PDFs.
  POST /api/liquidaciones/emitir  body: {periodo, enviar_email}
       → genera 1 PDF consolidado por propietario, lo guarda como Comprobante
         (tipo=propietario), opcionalmente envía email. Devuelve el lote.
"""
import base64
from datetime import date, datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models
from app.services.liquidacion_masiva import calcular_lote
from app.services.pdf_liquidacion_masiva import generar_pdf_liquidacion_consolidada
from app.services.email_service import enviar_email, smtp_configurado
from app.services import supabase_storage


router = APIRouter(prefix="/api/liquidaciones", tags=["liquidaciones"])


def _hoy_iso(): return f"{date.today().year}-{date.today().month:02d}"


@router.get("/preview")
def preview(mes: Optional[str] = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return calcular_lote(db, mes or _hoy_iso())


class EmitirIn(BaseModel):
    periodo: Optional[str] = None
    enviar_email: bool = True


@router.post("/emitir")
def emitir(data: EmitirIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    periodo = data.periodo or _hoy_iso()
    lote = calcular_lote(db, periodo)
    if not lote["propietarios"]:
        raise HTTPException(400, f"No hay pagos cobrados en {periodo} para liquidar")

    smtp_ok = smtp_configurado() if data.enviar_email else False
    salidas = []

    for idx, p in enumerate(lote["propietarios"], start=1):
        numero = f"LIQ-MES-{periodo}-{p['propietario_id']:04d}"

        # Vincular el lote a un Pago "ancla" (cualquier pago del propietario)
        # — la tabla `comprobantes` exige FK a un pago existente.
        ancla_pago_id = p["items"][0]["pago_id"] if p["items"] else None
        if ancla_pago_id is None:
            continue

        pdf = generar_pdf_liquidacion_consolidada({
            "numero": numero,
            "periodo": periodo,
            "fecha_emision": date.today(),
            "propietario": {
                "nombre": p["nombre"],
                "documento": p["documento"],
                "email": p["email"],
                "telefono": p["telefono"],
            },
            "items": p["items"],
            "totales": p["totales"],
        })

        # Subir PDF a Storage si está habilitado; fallback a base64 en DB.
        storage_path = None
        pdf_b64 = None
        if supabase_storage.enabled():
            sp = supabase_storage.gen_path(f"liquidacion-{periodo}", f"prop-{ancla_pago_id}.pdf")
            ok, info = supabase_storage.upload(
                supabase_storage.BUCKET_COMPROBANTES, sp, pdf, "application/pdf",
            )
            if ok:
                storage_path = info
            else:
                print(f"[liquidaciones] Storage upload falló: {info} — fallback base64")
                pdf_b64 = base64.b64encode(pdf).decode("ascii")
        else:
            pdf_b64 = base64.b64encode(pdf).decode("ascii")

        comp = models.Comprobante(
            pago_id=ancla_pago_id,
            tipo=models.ComprobanteTipo.propietario,
            destinatario_nombre=p["nombre"],
            destinatario_email=p["email"],
            monto_total=p["totales"]["cobrado_total"],
            monto_comision=p["totales"]["comision"],
            monto_neto=p["totales"]["neto"],
            pdf_blob=pdf_b64,
            storage_path=storage_path,
        )
        db.add(comp)
        db.flush()

        envio_ok = False
        envio_msg = "no enviado"
        if data.enviar_email and p["email"] and smtp_ok:
            asunto = f"Liquidación CIUDAD. — {periodo}"
            cuerpo = (
                f"Hola {p['nombre']},\n\n"
                f"Adjuntamos la liquidación consolidada del período {periodo}.\n\n"
                f"Cobrado: $ {p['totales']['cobrado_total']:,.2f}\n"
                f"Comisión: $ {p['totales']['comision']:,.2f}\n"
                f"Neto a transferir: $ {p['totales']['neto']:,.2f}\n\n"
                f"CIUDAD — Negocios Inmobiliarios"
            )
            envio_ok, envio_msg = enviar_email(
                p["email"], asunto, cuerpo, pdf, f"{numero}.pdf"
            )
            comp.enviado_email = envio_ok
            comp.fecha_envio = datetime.utcnow() if envio_ok else None
            comp.error_envio = None if envio_ok else envio_msg
        else:
            comp.enviado_email = False
            if not smtp_ok:
                comp.error_envio = "SMTP no configurado"
            elif not p["email"]:
                comp.error_envio = "Sin email destinatario"
            elif not data.enviar_email:
                comp.error_envio = "Envío de email desactivado en este lote"

        salidas.append({
            "propietario_id": p["propietario_id"],
            "propietario": p["nombre"],
            "comprobante_id": comp.id,
            "neto": p["totales"]["neto"],
            "cobrado_total": p["totales"]["cobrado_total"],
            "comision": p["totales"]["comision"],
            "email_destinatario": p["email"],
            "enviado_email": comp.enviado_email,
            "error_envio": comp.error_envio,
        })

    db.commit()

    return {
        "ok": True,
        "periodo": periodo,
        "smtp_configurado": smtp_ok,
        "total_propietarios": len(salidas),
        "monto_cobrado_total": lote["monto_cobrado_total"],
        "comision_total": lote["comision_total"],
        "neto_total_propietarios": lote["neto_total_propietarios"],
        "salidas": salidas,
    }
