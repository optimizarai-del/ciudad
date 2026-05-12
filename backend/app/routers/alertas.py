from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.security import get_current_user
from app import models
from app.services import notificaciones

router = APIRouter(prefix="/api/alertas", tags=["alertas"])


@router.get("/vencimientos")
def vencimientos(dias: int = 60, db: Session = Depends(get_db), user=Depends(get_current_user)):
    hoy = date.today()
    limite = hoy + timedelta(days=dias)

    contratos = (
        db.query(models.Contrato)
        .filter(
            models.Contrato.estado == models.ContratoEstado.vigente,
            models.Contrato.fecha_fin.isnot(None),
            models.Contrato.fecha_fin <= limite,
            models.Contrato.fecha_fin >= hoy,
        )
        .order_by(models.Contrato.fecha_fin)
        .all()
    )

    resultado = []
    for c in contratos:
        dias_restantes = (c.fecha_fin - hoy).days
        if dias_restantes <= 7:
            urgencia = "critico"
        elif dias_restantes <= 30:
            urgencia = "pronto"
        else:
            urgencia = "normal"

        prop = db.query(models.Propiedad).filter_by(id=c.propiedad_id).first()
        inquilino = db.query(models.Cliente).filter_by(id=c.inquilino_id).first() if c.inquilino_id else None

        resultado.append({
            "id": c.id,
            "codigo": c.codigo or f"#{c.id}",
            "tipo": c.tipo,
            "propiedad": prop.direccion if prop else f"Propiedad #{c.propiedad_id}",
            "inquilino": f"{inquilino.nombre} {inquilino.apellido or ''}".strip() if inquilino else None,
            "fecha_fin": c.fecha_fin.isoformat(),
            "dias_restantes": dias_restantes,
            "urgencia": urgencia,
        })

    return resultado


@router.get("/resumen")
def resumen(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Resumen tipo 'centro de notificaciones' para el panel de la campana.

    Junta varios tipos de alertas en un solo endpoint, ordenadas por
    urgencia, con link al detalle (contrato_id / propiedad_id) para que
    el frontend pueda navegar al click.
    """
    hoy = date.today()
    items = []

    # 1. Contratos VENCIDOS (estado = vencido)
    vencidos = (
        db.query(models.Contrato)
          .filter(models.Contrato.estado == models.ContratoEstado.vencido)
          .order_by(models.Contrato.fecha_fin.desc().nullslast())
          .limit(20)
          .all()
    )
    for c in vencidos:
        prop = db.query(models.Propiedad).filter_by(id=c.propiedad_id).first()
        dias_pasados = (hoy - c.fecha_fin).days if c.fecha_fin else None
        items.append({
            "id": f"contrato-vencido-{c.id}",
            "tipo": "contrato_vencido",
            "urgencia": "critico",
            "titulo": f"Contrato vencido — {prop.direccion if prop else f'#{c.id}'}",
            "descripcion": (
                f"Venció hace {dias_pasados} día{'s' if dias_pasados != 1 else ''}"
                if dias_pasados is not None else "Contrato vencido"
            ),
            "fecha": c.fecha_fin.isoformat() if c.fecha_fin else None,
            "link": f"/alquileres/contratos",
            "contrato_id": c.id,
            "propiedad_id": c.propiedad_id,
        })

    # 2. Contratos POR VENCER en los próximos 30 días
    limite = hoy + timedelta(days=30)
    por_vencer = (
        db.query(models.Contrato)
          .filter(
              models.Contrato.estado == models.ContratoEstado.vigente,
              models.Contrato.fecha_fin.isnot(None),
              models.Contrato.fecha_fin >= hoy,
              models.Contrato.fecha_fin <= limite,
          )
          .order_by(models.Contrato.fecha_fin)
          .limit(20)
          .all()
    )
    for c in por_vencer:
        prop = db.query(models.Propiedad).filter_by(id=c.propiedad_id).first()
        dias_restantes = (c.fecha_fin - hoy).days
        urgencia = "critico" if dias_restantes <= 7 else "pronto" if dias_restantes <= 30 else "normal"
        items.append({
            "id": f"contrato-vencer-{c.id}",
            "tipo": "contrato_por_vencer",
            "urgencia": urgencia,
            "titulo": f"Contrato por vencer — {prop.direccion if prop else f'#{c.id}'}",
            "descripcion": (
                f"Vence en {dias_restantes} día{'s' if dias_restantes != 1 else ''}"
                if dias_restantes > 0 else "Vence hoy"
            ),
            "fecha": c.fecha_fin.isoformat(),
            "link": f"/alquileres/contratos",
            "contrato_id": c.id,
            "propiedad_id": c.propiedad_id,
        })

    # 3. Pagos VENCIDOS o ATRASADOS — vencimiento pasado, sin fecha_pago
    pagos_atrasados = (
        db.query(models.Pago)
          .filter(
              models.Pago.estado.in_([models.PagoEstado.vencido, models.PagoEstado.pendiente]),
              models.Pago.fecha_pago.is_(None),
              models.Pago.fecha_vencimiento.isnot(None),
              models.Pago.fecha_vencimiento < hoy,
          )
          .order_by(models.Pago.fecha_vencimiento)
          .limit(30)
          .all()
    )
    for p in pagos_atrasados:
        contrato = db.query(models.Contrato).filter_by(id=p.contrato_id).first() if p.contrato_id else None
        prop = db.query(models.Propiedad).filter_by(id=contrato.propiedad_id).first() if contrato else None
        inquilino = db.query(models.Cliente).filter_by(id=contrato.inquilino_id).first() if contrato and contrato.inquilino_id else None
        dias_mora = (hoy - p.fecha_vencimiento).days
        items.append({
            "id": f"pago-mora-{p.id}",
            "tipo": "pago_mora",
            "urgencia": "critico" if dias_mora > 30 else "pronto",
            "titulo": f"Pago en mora — {prop.direccion if prop else f'Contrato #{p.contrato_id}'}",
            "descripcion": (
                f"{inquilino.nombre if inquilino else 'Inquilino'} debe ${(p.monto_total or 0):,.0f}".replace(",", ".")
                + f" · {dias_mora} día{'s' if dias_mora != 1 else ''} de atraso"
            ),
            "fecha": p.fecha_vencimiento.isoformat(),
            "link": f"/alquileres/cobranza",
            "contrato_id": p.contrato_id,
            "pago_id": p.id,
        })

    # 4. Eventos críticos de Recordatorios (loop background)
    eventos_crit = (
        db.query(models.Evento)
          .filter(models.Evento.es_critico.is_(True))
          .order_by(models.Evento.created_at.desc())
          .limit(10)
          .all()
    )
    for e in eventos_crit:
        items.append({
            "id": f"evento-{e.id}",
            "tipo": "evento_critico",
            "urgencia": "critico",
            "titulo": e.titulo,
            "descripcion": e.descripcion or "",
            "fecha": e.created_at.isoformat() if e.created_at else None,
            "link": "/recordatorios",
            "contrato_id": e.contrato_id,
            "propiedad_id": e.propiedad_id,
        })

    # Orden global: urgencia crítica primero, después por fecha más reciente
    urgencia_orden = {"critico": 0, "pronto": 1, "normal": 2}
    items.sort(key=lambda x: (urgencia_orden.get(x["urgencia"], 99), x.get("fecha") or ""))

    total_critico = sum(1 for x in items if x["urgencia"] == "critico")
    return {
        "total": len(items),
        "criticos": total_critico,
        "items": items[:50],   # cap defensivo
    }


@router.post("/enviar-recordatorios")
def enviar_recordatorios(dias: int = 60, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Envía emails de recordatorio para contratos por vencer. Retorna resumen."""
    hoy = date.today()
    limite = hoy + timedelta(days=dias)

    contratos = (
        db.query(models.Contrato)
        .filter(
            models.Contrato.estado == models.ContratoEstado.vigente,
            models.Contrato.fecha_fin.isnot(None),
            models.Contrato.fecha_fin <= limite,
            models.Contrato.fecha_fin >= hoy,
        )
        .order_by(models.Contrato.fecha_fin)
        .all()
    )

    enviados = 0
    fallidos = 0
    omitidos = 0

    for contrato in contratos:
        dias_restantes = (contrato.fecha_fin - hoy).days
        if not contrato.inquilino or not contrato.inquilino.email:
            omitidos += 1
            continue
        ok = notificaciones.enviar_recordatorio_vencimiento(contrato, dias_restantes)
        if ok:
            enviados += 1
        else:
            fallidos += 1

    return {
        "ok": True,
        "total_contratos": len(contratos),
        "enviados": enviados,
        "fallidos": fallidos,
        "omitidos": omitidos,
    }
