"""Inteligencia del Pipeline de Cliente (Fase 2).

- Degradación automática de temperatura por inactividad (doc §3.2) con aviso
  previo al vendedor.
- Consulta al líder antes de degradar (doc §7.1): la degradación NO es directa;
  se crea una consulta al líder y solo se ejecuta sola si no la responde en 24h.
- SLA por etapa (doc §3.4): alerta cuando un lead supera el tiempo máximo sin
  movimiento de su etapa.

Estas funciones las dispara el job diario (run_daily) o el endpoint manual.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import models_ventas as mv

# Umbrales de temperatura (días sin actividad). Doc §3.2.
TEMP_AVISO = {"caliente": 3, "tibio": 7}
TEMP_DEGRADA = {"caliente": 5, "tibio": 10}
TEMP_SIGUIENTE = {"caliente": "tibio", "tibio": "frio"}

# SLA por etapa en HORAS (None = sin SLA). Doc §3.4.
SLA_DEFAULT = {
    "nuevo_lead": 4,
    "en_calificacion": 48,
    "calificado_activo": None,        # según temperatura
    "presentacion_opciones": 120,     # 5 días
    "en_visitas": 72,                 # 3 días post-visita
    "oferta_negociacion": 24,
    "reserva_sena": None,
    "escritura_cierre": None,
    "caido_perdido": None,
    "frio_espera": 720,               # 30 días
}

ESTADOS_ACTIVOS = {
    "nuevo_lead", "en_calificacion", "calificado_activo", "presentacion_opciones",
    "en_visitas", "oferta_negociacion", "reserva_sena",
}


def _log(db, cliente_id, vendedor_id, tipo, de, a, detalle, automatico=True):
    db.add(mv.VentasClienteEvento(
        cliente_id=cliente_id, vendedor_id=vendedor_id, tipo=tipo, de=de, a=a,
        detalle=detalle, automatico=automatico))


def _dias_inactivo(c, ahora) -> float:
    base = c.ultimo_contacto_at or c.etapa_desde or c.created_at
    if not base:
        return 0
    return (ahora - base).total_seconds() / 86400.0


# ───────────────────────── degradación + consulta al líder ─────────────────────────

def correr_degradacion(db: Session, ahora: datetime | None = None) -> dict:
    """Avisa al vendedor cuando un lead se está por enfriar y, al cumplirse el
    plazo, crea una CONSULTA AL LÍDER (no degrada directo)."""
    ahora = ahora or datetime.utcnow()
    avisos, consultas = 0, 0
    clientes = (db.query(mv.VentasCliente)
                .filter(mv.VentasCliente.etapa.in_(ESTADOS_ACTIVOS))
                .filter(mv.VentasCliente.temperatura.in_(["caliente", "tibio"])).all())
    for c in clientes:
        dias = _dias_inactivo(c, ahora)
        temp = c.temperatura
        # ¿ya hay una consulta pendiente para este cliente? no duplicar
        pendiente = (db.query(mv.VentasLiderConsulta)
                     .filter_by(cliente_id=c.id, estado="pendiente").first())
        if pendiente:
            continue
        if dias >= TEMP_DEGRADA[temp]:
            # Crear consulta al líder (vence en 24h)
            db.add(mv.VentasLiderConsulta(
                cliente_id=c.id, vendedor_id=c.vendedor_id,
                de_temp=temp, a_temp=TEMP_SIGUIENTE[temp],
                estado="pendiente", creada_at=ahora, vence_at=ahora + timedelta(hours=24)))
            _log(db, c.id, c.vendedor_id, "degradacion", temp, TEMP_SIGUIENTE[temp],
                 f"Consulta al líder: {int(dias)}d sin actividad", automatico=True)
            consultas += 1
        elif dias >= TEMP_AVISO[temp] and not c.temp_alerta_previa_at:
            # Aviso previo al vendedor (una sola vez)
            c.temp_alerta_previa_at = ahora
            _log(db, c.id, c.vendedor_id, "sla", temp, temp,
                 f"Aviso: {int(dias)}d sin actividad, se está enfriando", automatico=True)
            avisos += 1
    db.commit()
    return {"avisos_previos": avisos, "consultas_creadas": consultas}


def resolver_consultas_vencidas(db: Session, ahora: datetime | None = None) -> dict:
    """Las consultas al líder no respondidas en 24h → degradación automática."""
    ahora = ahora or datetime.utcnow()
    degradados = 0
    vencidas = (db.query(mv.VentasLiderConsulta)
                .filter_by(estado="pendiente")
                .filter(mv.VentasLiderConsulta.vence_at <= ahora).all())
    for q in vencidas:
        c = db.get(mv.VentasCliente, q.cliente_id)
        if c and c.temperatura == q.de_temp:
            c.temperatura = q.a_temp
            c.temp_alerta_previa_at = None
            _log(db, c.id, c.vendedor_id, "temperatura", q.de_temp, q.a_temp,
                 "Degradación automática (líder no respondió en 24h)", automatico=True)
            degradados += 1
        q.estado = "auto"
        q.resuelta_at = ahora
        q.resolucion_detalle = "Sin respuesta del líder en 24h"
    db.commit()
    return {"degradados_auto": degradados}


def resolver_consulta(db: Session, consulta_id: int, accion: str,
                      detalle: str = "", reasignar_a: int | None = None) -> dict:
    """El líder resuelve una consulta: confirmar / posponer / reasignar."""
    q = db.get(mv.VentasLiderConsulta, consulta_id)
    if not q or q.estado != "pendiente":
        raise ValueError("Consulta no encontrada o ya resuelta.")
    ahora = datetime.utcnow()
    c = db.get(mv.VentasCliente, q.cliente_id)
    if accion == "confirmar":
        if c and c.temperatura == q.de_temp:
            c.temperatura = q.a_temp
            c.temp_alerta_previa_at = None
            _log(db, c.id, c.vendedor_id, "temperatura", q.de_temp, q.a_temp,
                 "Degradación confirmada por el líder", automatico=False)
        q.estado = "confirmada"
    elif accion == "posponer":
        if c:
            c.temp_alerta_previa_at = None  # reinicia el ciclo
            c.ultimo_contacto_at = ahora    # da aire
        q.estado = "pospuesta"
    elif accion == "reasignar":
        if c and reasignar_a:
            anterior = c.vendedor_id
            c.vendedor_id = reasignar_a
            c.temp_alerta_previa_at = None
            _log(db, c.id, reasignar_a, "reasignacion", str(anterior), str(reasignar_a),
                 detalle or "Reasignado por el líder", automatico=False)
        q.estado = "reasignada"
    else:
        raise ValueError("Acción inválida (confirmar | posponer | reasignar).")
    q.resolucion_detalle = detalle
    q.resuelta_at = ahora
    db.commit()
    return {"ok": True, "estado": q.estado}


# ───────────────────────── SLA ─────────────────────────

def get_sla_map(db: Session) -> dict:
    """SLA configurado por etapa; si no hay filas, devuelve los defaults."""
    filas = db.query(mv.VentasPipelineSLA).all()
    if not filas:
        return dict(SLA_DEFAULT)
    return {f.etapa: f.horas_sla for f in filas}


def seed_sla(db: Session):
    """Crea las filas de SLA por defecto si la tabla está vacía."""
    if db.query(mv.VentasPipelineSLA).count() > 0:
        return
    for etapa, horas in SLA_DEFAULT.items():
        db.add(mv.VentasPipelineSLA(etapa=etapa, horas_sla=horas))
    db.commit()


def sla_estado(c, sla_map: dict, ahora: datetime) -> dict:
    """Devuelve {vencido, horas_en_etapa, sla_horas} para un cliente."""
    horas_sla = sla_map.get(c.etapa)
    if not c.etapa_desde or not horas_sla:
        return {"sla_vencido": False, "sla_horas": horas_sla, "horas_en_etapa": None}
    horas = (ahora - c.etapa_desde).total_seconds() / 3600.0
    return {"sla_vencido": horas > horas_sla, "sla_horas": horas_sla,
            "horas_en_etapa": round(horas, 1)}


def run_pipeline_jobs(db: Session) -> dict:
    """Corre todo lo de Fase 2 de una: resolver vencidas → degradar/avisar."""
    seed_sla(db)
    r1 = resolver_consultas_vencidas(db)
    r2 = correr_degradacion(db)
    return {**r1, **r2}
