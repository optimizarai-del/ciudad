"""
Cobranza:
  GET   /api/cobranza/mensual?mes=YYYY-MM        — lista TODOS los contratos vigentes
                                                    con su pago del mes (existente o "pendiente").
  GET   /api/cobranza/resumen?mes=YYYY-MM        — totales cobrado/pendiente/vencido.
  PATCH /api/cobranza/{pago_id}/cobrar           — marcar pago como cobrado.
  POST  /api/cobranza/{contrato_id}/registrar-pago
        body: {periodo, fecha_pago, monto_alquiler, monto_expensas, monto_impuestos,
               monto_municipal, monto_otros, monto_total, notas}
        → crea/actualiza el Pago, genera 2 comprobantes PDF (inquilino + propietario),
          intenta enviarlos por email y los guarda en la base.
"""
import base64
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.security import get_current_user
from app import models
from app.services.pdf_comprobantes import (
    generar_pdf_comprobante_inquilino,
    generar_pdf_comprobante_propietario,
)
from app.services.email_service import enviar_email, smtp_configurado
from app.services import supabase_storage

router = APIRouter(prefix="/api/cobranza", tags=["cobranza"])


def _nombre_cliente(c: models.Cliente | None) -> str:
    if not c:
        return ""
    if c.razon_social:
        return c.razon_social
    return " ".join([p for p in [c.nombre, c.apellido] if p]) or ""


@router.get("/mensual")
def cobranza_mensual(mes: Optional[str] = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    Devuelve, para el mes pedido, una entrada por cada contrato vigente:
    si ya hay un Pago para ese período, devuelve sus datos; si no, marca estado='pendiente'.
    """
    if not mes:
        hoy = date.today()
        mes = f"{hoy.year}-{hoy.month:02d}"

    contratos = db.query(models.Contrato).filter(
        models.Contrato.estado == models.ContratoEstado.vigente
    ).all()

    result = []
    for c in contratos:
        prop = c.propiedad
        inq = c.inquilino
        propietario = prop.propietario if prop else None
        pago = (
            db.query(models.Pago)
            .filter(models.Pago.contrato_id == c.id, models.Pago.periodo == mes)
            .order_by(models.Pago.id.desc())
            .first()
        )

        # Componentes sugeridos para precargar el modal de "Registrar pago".
        # El usuario los puede editar antes de confirmar.
        alquiler_sug = float(c.monto_inicial or (prop.precio_alquiler if prop else 0) or 0)
        tasas_sug = float((prop.tasa_municipal if prop else 0) or 0) + float((prop.impuesto_inmobiliario if prop else 0) or 0)
        expensas_sug = float((prop.expensas if prop else 0) or 0)

        # Esperado total: si no hay pago, calculamos por contrato + costos asociados
        if pago:
            estado = pago.estado.value if hasattr(pago.estado, "value") else pago.estado
            monto_total = pago.monto_total or 0
            fecha_venc = pago.fecha_vencimiento.isoformat() if pago.fecha_vencimiento else None
            fecha_pago = pago.fecha_pago.isoformat() if pago.fecha_pago else None
        else:
            estado = "pendiente"
            monto_total = round(alquiler_sug + expensas_sug + tasas_sug, 2)
            fecha_venc = None
            fecha_pago = None

        result.append({
            "pago_id": pago.id if pago else None,
            "contrato_id": c.id,
            "contrato_codigo": c.codigo or f"#{c.id}",
            "propiedad_id": prop.id if prop else None,
            "propiedad": prop.direccion if prop else "",
            "propiedad_ciudad": prop.ciudad if prop else "",
            "inquilino_id": inq.id if inq else None,
            "inquilino": _nombre_cliente(inq) or "Sin inquilino",
            "inquilino_email": inq.email if inq else None,
            "inquilino_telefono": inq.telefono if inq else None,
            "propietario_id": propietario.id if propietario else None,
            "propietario": _nombre_cliente(propietario) or "Sin propietario",
            "propietario_email": propietario.email if propietario else None,
            "comision_porc": c.comision_porc or 0,
            "monto_total": monto_total,
            "monto_alquiler_sug": round(alquiler_sug, 2),
            "monto_expensas_sug": round(expensas_sug, 2),
            "monto_tasas_sug": round(tasas_sug, 2),
            "fecha_vencimiento": fecha_venc,
            "fecha_pago": fecha_pago,
            "estado": estado,
            "periodo": mes,
        })

    return result


@router.patch("/{pago_id}/cobrar")
def marcar_cobrado(pago_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    pago = db.query(models.Pago).get(pago_id)
    if not pago:
        raise HTTPException(404, "Pago no encontrado")
    pago.estado = models.PagoEstado.pagado
    pago.fecha_pago = date.today()
    db.commit()
    return {"ok": True, "fecha_pago": pago.fecha_pago.isoformat()}


@router.get("/resumen")
def resumen_cobranza(mes: Optional[str] = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    Suma cobrado/pendiente/vencido del mes.
    Importante: los contratos vigentes que aún no tienen Pago registrado para
    el período cuentan como `pendiente` (con el monto esperado calculado a
    partir del contrato + costos de la propiedad). Si no fuera así, un mes
    sin pagos cargados se reportaba erróneamente como "100% cobrado".
    """
    if not mes:
        hoy = date.today()
        mes = f"{hoy.year}-{hoy.month:02d}"

    contratos = db.query(models.Contrato).filter(
        models.Contrato.estado == models.ContratoEstado.vigente
    ).all()

    cobrado = pendiente = vencido = 0.0
    pagos_count = 0

    for c in contratos:
        pago = (
            db.query(models.Pago)
            .filter(models.Pago.contrato_id == c.id, models.Pago.periodo == mes)
            .order_by(models.Pago.id.desc())
            .first()
        )
        if pago:
            pagos_count += 1
            monto = pago.monto_total or 0
            if pago.estado == models.PagoEstado.pagado:
                cobrado += monto
            elif pago.estado == models.PagoEstado.vencido:
                vencido += monto
            else:
                pendiente += monto
        else:
            # Sin pago registrado → estimación del esperado para que la barra
            # de cobranza tenga base real.
            prop = c.propiedad
            base = float(c.monto_inicial or (prop.precio_alquiler if prop else 0) or 0)
            tasas = (prop.tasa_municipal if prop else 0) + (prop.impuesto_inmobiliario if prop else 0)
            extras = (prop.expensas if prop else 0) + (tasas or 0)
            pendiente += round(base + (extras or 0), 2)

    total = cobrado + pendiente + vencido

    return {
        "mes": mes,
        "cobrado": cobrado,
        "pendiente": pendiente,
        "vencido": vencido,
        "total_esperado": total,
        "porcentaje_cobrado": round((cobrado / total * 100) if total > 0 else 0, 1),
        "contratos_activos": len(contratos),
        "pagos_count": pagos_count,
    }


# ────────────────────────────────────────────────────────────────────
# Registrar pago + comprobantes
# ────────────────────────────────────────────────────────────────────

class RegistrarPagoIn(BaseModel):
    periodo: Optional[str] = None             # YYYY-MM
    fecha_pago: Optional[date] = None
    monto_alquiler: float = 0
    monto_expensas: float = 0
    monto_impuestos: float = 0
    monto_municipal: float = 0
    monto_otros: float = 0
    monto_total: Optional[float] = None
    notas: Optional[str] = None


def _crear_comprobante(db: Session, pago: models.Pago, tipo: models.ComprobanteTipo,
                       nombre: str, email: Optional[str],
                       pdf_bytes: bytes, monto_total: float,
                       monto_comision: float = 0, monto_neto: float = 0,
                       enviar_mail: bool = True,
                       asunto: str = "", cuerpo: str = "") -> models.Comprobante:
    # Subir el PDF a Supabase Storage si está habilitado; fallback a blob en DB.
    storage_path = None
    pdf_b64 = None
    if pdf_bytes:
        if supabase_storage.enabled():
            sp = supabase_storage.gen_path(f"pago-{pago.id}", f"{tipo.value}.pdf")
            ok, info = supabase_storage.upload(
                supabase_storage.BUCKET_COMPROBANTES, sp, pdf_bytes, "application/pdf",
            )
            if ok:
                storage_path = info
            else:
                print(f"[cobranza] Storage upload falló: {info} — fallback base64")
                pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
        else:
            pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")

    comp = models.Comprobante(
        pago_id=pago.id,
        tipo=tipo,
        destinatario_nombre=nombre,
        destinatario_email=email,
        monto_total=monto_total,
        monto_comision=monto_comision,
        monto_neto=monto_neto,
        pdf_blob=pdf_b64,
        storage_path=storage_path,
    )
    db.add(comp)
    db.flush()  # obtener id antes del envío

    if enviar_mail and email and smtp_configurado():
        ok, msg = enviar_email(
            email, asunto, cuerpo, pdf_bytes, f"comprobante-{tipo.value}-{comp.id}.pdf"
        )
        comp.enviado_email = ok
        comp.fecha_envio = datetime.utcnow() if ok else None
        comp.error_envio = None if ok else msg
    else:
        comp.enviado_email = False
        comp.error_envio = "SMTP no configurado" if not smtp_configurado() else "Sin email destinatario"
    return comp


@router.post("/{contrato_id}/registrar-pago")
def registrar_pago(
    contrato_id: int,
    data: RegistrarPagoIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    contrato = db.query(models.Contrato).filter_by(id=contrato_id).first()
    if not contrato:
        raise HTTPException(404, "Contrato no encontrado")
    propiedad = contrato.propiedad
    inquilino = contrato.inquilino
    propietario = propiedad.propietario if propiedad else None

    # Período
    fecha_pago = data.fecha_pago or date.today()
    periodo = data.periodo or f"{fecha_pago.year}-{fecha_pago.month:02d}"

    # Monto total auto si vino vacío.
    # Tasas municipales agrupa lo que históricamente se separaba en impuestos + municipal.
    tasas_municipales = float(data.monto_impuestos or 0) + float(data.monto_municipal or 0)
    items = [
        ("Alquiler", data.monto_alquiler),
        ("Expensas", data.monto_expensas),
        ("Tasas municipales", tasas_municipales),
        ("Otros conceptos", data.monto_otros),
    ]
    items_no_cero = [(l, v) for l, v in items if v and v > 0]
    monto_total = data.monto_total if data.monto_total is not None else sum(v for _, v in items_no_cero)

    # Crear o actualizar el pago
    pago = (
        db.query(models.Pago)
        .filter(models.Pago.contrato_id == contrato.id, models.Pago.periodo == periodo)
        .first()
    )
    if pago is None:
        pago = models.Pago(contrato_id=contrato.id, periodo=periodo)
        db.add(pago)
    pago.fecha_pago = fecha_pago
    pago.monto_alquiler = data.monto_alquiler
    pago.monto_expensas = data.monto_expensas
    pago.monto_impuestos = data.monto_impuestos
    pago.monto_municipal = data.monto_municipal
    pago.monto_otros = data.monto_otros
    pago.monto_total = monto_total
    pago.estado = models.PagoEstado.pagado
    pago.notas = data.notas
    db.flush()

    # Comisión inmobiliaria: se calcula SOLO sobre el alquiler, no sobre los
    # gastos pasantes (expensas, tasas, otros). El propietario percibe
    # alquiler − comisión; las demás partidas las cobra el inquilino y se
    # derivan a quien corresponda (consorcio, municipio, etc).
    monto_alquiler = float(data.monto_alquiler or 0)
    comision_pct = float(contrato.comision_porc or 0)
    comision = round(monto_alquiler * comision_pct / 100.0, 2)
    neto = round(monto_alquiler - comision, 2)
    items_pasantes = [(l, v) for l, v in items_no_cero if l != "Alquiler"]

    nombre_inq = _nombre_cliente(inquilino) or "Inquilino/a"
    nombre_pro = _nombre_cliente(propietario) or "Propietario/a"
    prop_ctx = {
        "direccion": propiedad.direccion if propiedad else "—",
        "ciudad": propiedad.ciudad if propiedad else "—",
        "codigo": propiedad.codigo if propiedad else None,
    }
    contrato_ctx = {"id": contrato.id, "codigo": contrato.codigo}

    # PDF inquilino
    pdf_inq = generar_pdf_comprobante_inquilino({
        "numero": f"REC-{periodo}-{contrato.id:04d}",
        "fecha_pago": fecha_pago,
        "periodo": periodo,
        "propiedad": prop_ctx,
        "contrato": contrato_ctx,
        "inquilino": {
            "nombre_completo": nombre_inq,
            "documento": inquilino.documento if inquilino else None,
            "email": inquilino.email if inquilino else None,
            "telefono": inquilino.telefono if inquilino else None,
        },
        "items": items_no_cero or [("Pago del período", monto_total)],
        "total": monto_total,
    })

    # PDF propietario — incluye desglose de lo cobrado al inquilino y la
    # liquidación calculada sobre el alquiler.
    pdf_pro = generar_pdf_comprobante_propietario({
        "numero": f"LIQ-{periodo}-{contrato.id:04d}",
        "fecha_pago": fecha_pago,
        "periodo": periodo,
        "propiedad": prop_ctx,
        "contrato": contrato_ctx,
        "propietario": {
            "nombre_completo": nombre_pro,
            "documento": propietario.documento if propietario else None,
            "email": propietario.email if propietario else None,
            "telefono": propietario.telefono if propietario else None,
        },
        "inquilino": {"nombre_completo": nombre_inq},
        "items_cobrados": items_no_cero or [("Pago del período", monto_total)],
        "items_pasantes": items_pasantes,
        "monto_alquiler": monto_alquiler,
        "monto_cobrado_total": monto_total,
        "comision_porc": comision_pct,
        "monto_comision": comision,
        "monto_neto": neto,
    })

    # Crear comprobantes
    cuerpo_inq = (
        f"Hola {nombre_inq},\n\n"
        f"Adjuntamos el recibo del pago correspondiente al período {periodo} "
        f"por la propiedad {prop_ctx['direccion']}.\n\n"
        f"Total abonado: $ {monto_total:,.2f}\n\n"
        f"¡Gracias!\nCIUDAD."
    )
    cuerpo_pro = (
        f"Hola {nombre_pro},\n\n"
        f"Te enviamos la liquidación del período {periodo} correspondiente a "
        f"{prop_ctx['direccion']}.\n\n"
        f"Total cobrado al inquilino: $ {monto_total:,.2f}\n"
        f"Alquiler base: $ {monto_alquiler:,.2f}\n"
        f"Comisión ({comision_pct}% sobre alquiler): $ {comision:,.2f}\n"
        f"Neto a transferir: $ {neto:,.2f}\n\n"
        f"CIUDAD."
    )

    comp_inq = _crear_comprobante(
        db, pago, models.ComprobanteTipo.inquilino,
        nombre_inq, inquilino.email if inquilino else None,
        pdf_inq, monto_total,
        asunto=f"Recibo CIUDAD. — {periodo}", cuerpo=cuerpo_inq,
    )
    comp_pro = _crear_comprobante(
        db, pago, models.ComprobanteTipo.propietario,
        nombre_pro, propietario.email if propietario else None,
        pdf_pro, monto_total, monto_comision=comision, monto_neto=neto,
        asunto=f"Liquidación CIUDAD. — {periodo}", cuerpo=cuerpo_pro,
    )
    db.commit()

    return {
        "ok": True,
        "pago_id": pago.id,
        "periodo": periodo,
        "monto_total": monto_total,
        "comision": comision,
        "neto_propietario": neto,
        "smtp_configurado": smtp_configurado(),
        "comprobantes": [
            {
                "id": comp_inq.id,
                "tipo": "inquilino",
                "destinatario": nombre_inq,
                "email": inquilino.email if inquilino else None,
                "enviado_email": comp_inq.enviado_email,
                "error": comp_inq.error_envio,
            },
            {
                "id": comp_pro.id,
                "tipo": "propietario",
                "destinatario": nombre_pro,
                "email": propietario.email if propietario else None,
                "enviado_email": comp_pro.enviado_email,
                "error": comp_pro.error_envio,
            },
        ],
    }
