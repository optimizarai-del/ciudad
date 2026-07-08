"""
Captación multicanal de leads (Fase 4.2 / 4.3).

Punto de entrada único para los leads que llegan por canales externos
(Instagram DM, WhatsApp, formularios web…). Cada mensaje entrante se convierte
en un `VentasCliente` en etapa `nuevo_lead`, con:

  - asignación automática al vendedor menos cargado (round-robin),
  - una nota con el primer mensaje recibido,
  - un evento de pipeline ("Lead creado" por <canal>),
  - una notificación al vendedor asignado (web + Telegram).

Es idempotente por (canal, identificador de contacto): si el mismo contacto
vuelve a escribir en una ventana corta, NO se crea un lead nuevo — se agrega la
nota al lead existente. Así un hilo de WhatsApp no genera 20 leads.

No depende de credenciales para funcionar: el router de webhooks valida el
token del canal; este servicio solo persiste. Si no hay ningún vendedor
cargado todavía, el lead se crea igual sin asignar (vendedor_id = None).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models_ventas as mv
from app.services import ventas_notif


# Ventana en la que un mismo contacto no genera un lead nuevo (mismo hilo).
_DEDUPE_HORAS = 72


def _elegir_vendedor(db: Session) -> Optional[mv.VentasVendedor]:
    """Round-robin simple: el vendedor activo con menos clientes asignados.

    Prioriza vendedores NO admin (los admin ven todo igual y no suelen tomar el
    lead inicial). Si solo hay admins, usa el admin. Si no hay ninguno, None.
    """
    # Los leads entrantes son reales → nunca se asignan al vendedor demo.
    vendedores = db.query(mv.VentasVendedor).filter(
        mv.VentasVendedor.activo.is_(True),
        mv.VentasVendedor.is_demo.is_(False),
    ).all()
    if not vendedores:
        return None

    no_admin = [v for v in vendedores if not v.es_admin]
    candidatos = no_admin or vendedores

    # Conteo de clientes por vendedor (una sola query).
    conteos = dict(
        db.query(mv.VentasCliente.vendedor_id, func.count(mv.VentasCliente.id))
        .group_by(mv.VentasCliente.vendedor_id).all()
    )
    return min(candidatos, key=lambda v: conteos.get(v.id, 0))


def _lead_existente(db: Session, origen: str, telefono: Optional[str],
                    email: Optional[str], handle: Optional[str]) -> Optional[mv.VentasCliente]:
    """Busca un lead reciente del mismo contacto por el mismo canal."""
    ident = [x for x in (telefono, email, handle) if x]
    if not ident:
        return None
    desde = datetime.utcnow() - timedelta(hours=_DEDUPE_HORAS)
    q = db.query(mv.VentasCliente).filter(mv.VentasCliente.created_at >= desde)
    filtros = []
    if telefono:
        filtros.append(mv.VentasCliente.telefono == telefono)
    if email:
        filtros.append(mv.VentasCliente.email == email)
    if filtros:
        from sqlalchemy import or_
        return q.filter(or_(*filtros)).order_by(mv.VentasCliente.id.desc()).first()
    return None


def crear_lead_entrante(
    db: Session,
    *,
    nombre: str,
    origen: str,
    telefono: Optional[str] = None,
    email: Optional[str] = None,
    handle: Optional[str] = None,
    mensaje: Optional[str] = None,
) -> dict:
    """Crea (o reactiva) un lead entrante. NO hace commit — lo deja al caller.

    Devuelve {"cliente_id", "nuevo": bool, "vendedor_id"}.
    """
    nombre = (nombre or "").strip() or (handle or telefono or email or "Lead sin nombre")
    origen = (origen or "externo").strip().lower()

    existente = _lead_existente(db, origen, telefono, email, handle)
    if existente:
        if mensaje:
            db.add(mv.VentasClienteNota(
                cliente_id=existente.id, vendedor_id=existente.vendedor_id,
                texto=f"[{origen}] {mensaje}"[:2000], origen=origen))
            existente.ultimo_contacto_at = datetime.utcnow()
        db.flush()
        return {"cliente_id": existente.id, "nuevo": False,
                "vendedor_id": existente.vendedor_id}

    vendedor = _elegir_vendedor(db)
    ahora = datetime.utcnow()
    cli = mv.VentasCliente(
        nombre=nombre,
        telefono=telefono,
        email=email,
        origen=origen,
        vendedor_id=vendedor.id if vendedor else None,
        etapa=mv.ClienteEtapa.nuevo_lead.value,
        temperatura=mv.ClienteTemperatura.tibio.value,
        etapa_desde=ahora,
        ultimo_contacto_at=ahora,
        observaciones=(f"Handle: {handle}" if handle else None),
    )
    db.add(cli)
    db.flush()

    # Nota con el primer mensaje.
    if mensaje:
        db.add(mv.VentasClienteNota(
            cliente_id=cli.id, vendedor_id=cli.vendedor_id,
            texto=f"[{origen}] {mensaje}"[:2000], origen=origen))

    # Evento de pipeline (timeline + métricas).
    db.add(mv.VentasClienteEvento(
        cliente_id=cli.id, vendedor_id=cli.vendedor_id,
        tipo="etapa", de=None, a=mv.ClienteEtapa.nuevo_lead.value,
        detalle=f"Lead creado por {origen}", automatico=True))

    # Notificación al vendedor asignado.
    if vendedor:
        try:
            ventas_notif.crear_notificacion(
                db, vendedor.id, tipo="asignacion",
                titulo=f"🆕 Nuevo lead por {origen}",
                cuerpo=f"{nombre}" + (f" · {telefono}" if telefono else ""),
                payload={"cliente_id": cli.id, "origen": origen})
        except Exception as e:
            print(f"[ventas_captacion] notif fallback: {e}")

    db.flush()
    return {"cliente_id": cli.id, "nuevo": True,
            "vendedor_id": cli.vendedor_id}
