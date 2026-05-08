"""
Scheduler interno de recordatorios.

No requiere cron externo: usa asyncio.create_task() en el startup. Cada
ciclo (default 1 vez/hora) revisa:

  • Contratos por vencer en ≤7 / ≤30 / ≤60 días → alerta crítica/aviso.
  • Pagos vencidos sin saldar → mora.
  • Contratos con próximo ajuste de canon → recordatorio operativo.

Las alertas se persisten en la tabla `Evento` (es_critico=True para 7d y mora)
y se mandan por Telegram a los chats admin (TELEGRAM_ADMIN_CHATS) y por email
a SMTP_FROM si está configurado. Idempotente: no duplica eventos del mismo
día para el mismo contrato/pago.
"""
import asyncio
import logging
import os
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app import models
from app.database import SessionLocal
from app.services import telegram_service
from app.services.email_service import enviar_email, smtp_configurado


log = logging.getLogger("ciudad.recordatorios")


def _ya_avisado_hoy(db: Session, contrato_id: int = None, pago_id: int = None,
                    titulo_match: str = None) -> bool:
    """¿Hay un Evento creado hoy con esa misma combinación?"""
    hoy = date.today()
    q = db.query(models.Evento).filter(
        models.Evento.created_at >= datetime(hoy.year, hoy.month, hoy.day)
    )
    if contrato_id:
        q = q.filter(models.Evento.contrato_id == contrato_id)
    if pago_id:
        # Eventos no se vinculan directo a Pago, pero el título contiene el id.
        q = q.filter(models.Evento.titulo.like(f"%pago#{pago_id}%"))
    if titulo_match:
        q = q.filter(models.Evento.titulo.like(f"%{titulo_match}%"))
    return q.count() > 0


def _crear_evento(db: Session, titulo: str, descripcion: str = None,
                  tipo=models.EventoTipo.vencimiento, contrato_id: int = None,
                  propiedad_id: int = None, es_critico: bool = False) -> models.Evento:
    ev = models.Evento(
        tipo=tipo,
        titulo=titulo,
        descripcion=descripcion,
        contrato_id=contrato_id,
        propiedad_id=propiedad_id,
        es_critico=es_critico,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


async def _broadcast(texto: str, asunto_email: str = "CIUDAD — Recordatorio"):
    """Manda el texto a los chats admin y al email del staff (si configurado)."""
    chats = [c.strip() for c in os.getenv("TELEGRAM_ADMIN_CHATS", "").split(",") if c.strip()]
    for chat_id in chats:
        try:
            await telegram_service.send_message(chat_id, texto)
        except Exception as e:
            log.warning(f"No se pudo enviar Telegram a {chat_id}: {e}")

    staff_email = os.getenv("STAFF_EMAIL")
    if smtp_configurado() and staff_email:
        ok, _ = enviar_email(staff_email, asunto_email, texto)
        if not ok:
            log.warning("Falló envío de recordatorio por email")


def _ejecutar_ciclo_sync(db: Session) -> dict:
    """Ejecuta un ciclo y devuelve qué se generó. Sincrónico para test."""
    hoy = date.today()
    eventos_creados = []
    mensajes = []

    # ── 1. Contratos por vencer ──────────────────────────────────────────────
    contratos = (
        db.query(models.Contrato)
        .filter(models.Contrato.estado == models.ContratoEstado.vigente)
        .filter(models.Contrato.fecha_fin.isnot(None))
        .all()
    )
    for c in contratos:
        dias = (c.fecha_fin - hoy).days
        if dias < 0 or dias > 60:
            continue
        if dias <= 7:
            urgencia = "CRÍTICO"
            es_critico = True
            tag = "vence-7d"
        elif dias <= 30:
            urgencia = "Próximo"
            es_critico = False
            tag = "vence-30d"
        else:
            urgencia = "Aviso"
            es_critico = False
            tag = "vence-60d"

        if _ya_avisado_hoy(db, contrato_id=c.id, titulo_match=tag):
            continue

        prop = c.propiedad
        titulo = f"[{urgencia}/{tag}] Contrato {c.codigo or c.id} vence en {dias} días"
        desc = (
            f"Propiedad: {prop.direccion if prop else '—'}. "
            f"Vencimiento: {c.fecha_fin}. Estado: {c.estado.value if hasattr(c.estado,'value') else c.estado}."
        )
        ev = _crear_evento(db, titulo, desc, models.EventoTipo.vencimiento,
                           contrato_id=c.id, propiedad_id=c.propiedad_id, es_critico=es_critico)
        eventos_creados.append(ev.id)
        mensajes.append(f"⚠ {titulo}\n{desc}")

    # ── 2. Pagos en mora ────────────────────────────────────────────────────
    pagos_morosos = (
        db.query(models.Pago)
        .filter(or_(
            models.Pago.estado == models.PagoEstado.vencido,
            models.Pago.estado == models.PagoEstado.pendiente,
        ))
        .filter(models.Pago.fecha_vencimiento.isnot(None))
        .filter(models.Pago.fecha_vencimiento < hoy)
        .all()
    )
    for p in pagos_morosos:
        if p.estado == models.PagoEstado.pagado:
            continue
        tag = f"mora-pago#{p.id}"
        if _ya_avisado_hoy(db, contrato_id=p.contrato_id, titulo_match=tag):
            continue
        c = p.contrato
        prop = c.propiedad if c else None
        dias_atraso = (hoy - p.fecha_vencimiento).days
        titulo = f"[MORA/{tag}] Pago {p.periodo or '—'} con {dias_atraso} días de atraso"
        desc = (
            f"Contrato: {c.codigo if c else '—'}. "
            f"Propiedad: {prop.direccion if prop else '—'}. "
            f"Monto adeudado: $ {p.monto_total or 0:,.2f}."
        )
        ev = _crear_evento(db, titulo, desc, models.EventoTipo.vencimiento,
                           contrato_id=p.contrato_id,
                           propiedad_id=prop.id if prop else None,
                           es_critico=dias_atraso > 5)
        eventos_creados.append(ev.id)
        mensajes.append(f"💰 {titulo}\n{desc}")

    # ── 3. Próximos ajustes de canon ────────────────────────────────────────
    for c in contratos:
        if not c.fecha_inicio or not c.periodicidad_meses:
            continue
        if (c.indice_ajuste.value if hasattr(c.indice_ajuste, "value") else c.indice_ajuste) == "sin_ajuste":
            continue
        # Próxima fecha de ajuste = fecha_inicio + N * periodicidad_meses (la primera
        # que sea ≥ hoy).
        per = c.periodicidad_meses
        n = 1
        anio, mes = c.fecha_inicio.year, c.fecha_inicio.month + per
        while True:
            while mes > 12:
                mes -= 12
                anio += 1
            try:
                fecha_aj = date(anio, mes, c.fecha_inicio.day)
            except ValueError:
                fecha_aj = date(anio, mes, 28)
            if fecha_aj >= hoy:
                break
            mes += per
            n += 1
            if n > 60:  # safety
                break
        dias_a_ajuste = (fecha_aj - hoy).days
        if 0 <= dias_a_ajuste <= 7:
            tag = f"ajuste-{fecha_aj.isoformat()}"
            if _ya_avisado_hoy(db, contrato_id=c.id, titulo_match=tag):
                continue
            titulo = f"[Ajuste/{tag}] Contrato {c.codigo or c.id} ajusta el {fecha_aj}"
            desc = (
                f"Índice: {c.indice_ajuste.value if hasattr(c.indice_ajuste,'value') else c.indice_ajuste}. "
                f"Período: {per} meses. Días para ajustar: {dias_a_ajuste}."
            )
            ev = _crear_evento(db, titulo, desc, models.EventoTipo.ajuste,
                               contrato_id=c.id, propiedad_id=c.propiedad_id,
                               es_critico=False)
            eventos_creados.append(ev.id)
            mensajes.append(f"📊 {titulo}\n{desc}")

    return {"eventos_creados": eventos_creados, "mensajes": mensajes,
            "fecha": hoy.isoformat()}


async def correr_un_ciclo() -> dict:
    """Ejecuta un ciclo completo y broadcastea los avisos."""
    db = SessionLocal()
    try:
        out = _ejecutar_ciclo_sync(db)
    finally:
        db.close()
    if out["mensajes"]:
        bloque = "\n\n".join(out["mensajes"])
        cabecera = f"📋 Recordatorios CIUDAD — {date.today().isoformat()}"
        await _broadcast(f"{cabecera}\n\n{bloque}")
    return out


async def loop_recordatorios(intervalo_seg: int = 3600):
    """Loop infinito ejecutando ciclos cada `intervalo_seg`. Default 1h."""
    while True:
        try:
            await correr_un_ciclo()
        except Exception as e:
            log.exception(f"Error en ciclo de recordatorios: {e}")
        await asyncio.sleep(intervalo_seg)
