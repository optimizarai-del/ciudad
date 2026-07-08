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


# ═══════════════════════ Fase 3 · métricas del pipeline ═══════════════════════

# Orden canónico de las 8 etapas activas (índice = avance).
ETAPAS_ACTIVAS_ORDEN = [e.value for e in mv.CLIENTE_ETAPAS_ORDEN]

# Probabilidad de cierre ponderada por etapa: valora el pipeline (valor esperado).
PROB_ETAPA = {
    "nuevo_lead": 0.05,
    "en_calificacion": 0.10,
    "calificado_activo": 0.20,
    "presentacion_opciones": 0.35,
    "en_visitas": 0.50,
    "oferta_negociacion": 0.70,
    "reserva_sena": 0.90,
    "escritura_cierre": 1.0,
    "caido_perdido": 0.0,
    "frio_espera": 0.0,
}

ETIQUETA_ETAPA = {
    "nuevo_lead": "Nuevo lead",
    "en_calificacion": "En calificación",
    "calificado_activo": "Calificado · activo",
    "presentacion_opciones": "Presentación de opciones",
    "en_visitas": "En visitas",
    "oferta_negociacion": "Oferta · negociación",
    "reserva_sena": "Reserva · seña",
    "escritura_cierre": "Escritura · cierre",
    "caido_perdido": "Caído · perdido",
    "frio_espera": "Frío · en espera",
}


def valor_cliente(c) -> float:
    """Valor estimado de la operación del cliente: punto medio del presupuesto."""
    lo, hi = c.presupuesto_min_usd, c.presupuesto_max_usd
    if lo and hi:
        return (lo + hi) / 2.0
    return float(hi or lo or 0)


def _riesgo_cliente(c, sla_map, ahora, en_consulta) -> dict:
    """Flags de riesgo de un cliente activo (para dashboard y vista líder)."""
    prox = c.proxima_accion_fecha
    return {
        "sin_proxima_accion": not c.proxima_accion_fecha,
        "proxima_accion_vencida": bool(prox and prox < ahora),
        "sla_vencido": sla_estado(c, sla_map, ahora)["sla_vencido"],
        "en_consulta_lider": c.id in en_consulta,
    }


def metricas(db: Session, clientes: list, ahora: datetime | None = None) -> dict:
    """Métricas agregadas del pipeline sobre un set de clientes ya scopeado.

    - distribucion_etapa: foto actual (kanban) por etapa activa.
    - embudo: cuántos clientes ALCANZARON al menos cada etapa (acumulado, desde
      el historial de eventos) → permite ver conversión etapa a etapa.
    - conversion: % de paso entre etapas consecutivas.
    - temperatura: caliente/tibio/frío.
    - tiempo_promedio_etapa: días promedio en la etapa actual.
    - riesgo: sin próxima acción / acción vencida / SLA vencido.
    - valor: total y ponderado por probabilidad de cierre.
    """
    ahora = ahora or datetime.utcnow()
    sla_map = get_sla_map(db)
    en_consulta = {q.cliente_id for q in db.query(mv.VentasLiderConsulta.cliente_id)
                   .filter(mv.VentasLiderConsulta.estado == "pendiente")}
    idx = {e: i for i, e in enumerate(ETAPAS_ACTIVAS_ORDEN)}

    distribucion = {e: 0 for e in ETAPAS_ACTIVAS_ORDEN}
    pausa = {e.value: 0 for e in mv.CLIENTE_ETAPAS_PAUSA}
    temperatura = {"caliente": 0, "tibio": 0, "frio": 0}
    dias_por_etapa = {e: [] for e in ETAPAS_ACTIVAS_ORDEN}
    riesgo = {"sin_proxima_accion": 0, "proxima_accion_vencida": 0,
              "sla_vencido": 0, "en_consulta_lider": 0}
    valor_total = 0.0
    valor_ponderado = 0.0

    # Base del embudo: todos los clientes "alcanzaron" al menos nuevo_lead (idx 0).
    alcanzado_max = {c.id: 0 for c in clientes}

    activos = 0
    for c in clientes:
        etapa = c.etapa or "nuevo_lead"
        temperatura[c.temperatura or "tibio"] = temperatura.get(c.temperatura or "tibio", 0) + 1
        if etapa in distribucion:
            distribucion[etapa] += 1
            activos += 1
            if c.etapa_desde:
                dias_por_etapa[etapa].append((ahora - c.etapa_desde).total_seconds() / 86400.0)
            r = _riesgo_cliente(c, sla_map, ahora, en_consulta)
            for k in riesgo:
                if r[k]:
                    riesgo[k] += 1
            v = valor_cliente(c)
            valor_total += v
            valor_ponderado += v * PROB_ETAPA.get(etapa, 0.0)
            alcanzado_max[c.id] = max(alcanzado_max[c.id], idx.get(etapa, 0))
        elif etapa in pausa:
            pausa[etapa] += 1

    # Embudo acumulado desde el historial de etapas (eventos tipo="etapa").
    cids = [c.id for c in clientes]
    if cids:
        eventos = (db.query(mv.VentasClienteEvento)
                   .filter(mv.VentasClienteEvento.tipo == "etapa")
                   .filter(mv.VentasClienteEvento.cliente_id.in_(cids)).all())
        for ev in eventos:
            for val in (ev.de, ev.a):
                if val in idx and ev.cliente_id in alcanzado_max:
                    alcanzado_max[ev.cliente_id] = max(alcanzado_max[ev.cliente_id], idx[val])

    embudo = []
    for i, e in enumerate(ETAPAS_ACTIVAS_ORDEN):
        n = sum(1 for mx in alcanzado_max.values() if mx >= i)
        embudo.append({"etapa": e, "label": ETIQUETA_ETAPA[e], "alcanzaron": n})
    conversion = []
    for i in range(len(embudo) - 1):
        a, b = embudo[i]["alcanzaron"], embudo[i + 1]["alcanzaron"]
        conversion.append({
            "de": embudo[i]["etapa"], "a": embudo[i + 1]["etapa"],
            "pct": round(100.0 * b / a, 1) if a else 0.0,
        })

    tiempo_promedio = {
        e: (round(sum(v) / len(v), 1) if v else None)
        for e, v in dias_por_etapa.items()
    }

    return {
        "total_clientes": len(clientes),
        "activos": activos,
        "distribucion_etapa": [
            {"etapa": e, "label": ETIQUETA_ETAPA[e], "n": distribucion[e]}
            for e in ETAPAS_ACTIVAS_ORDEN
        ],
        "en_pausa": [
            {"etapa": e, "label": ETIQUETA_ETAPA[e], "n": pausa[e]} for e in pausa
        ],
        "temperatura": temperatura,
        "embudo": embudo,
        "conversion": conversion,
        "tiempo_promedio_etapa": tiempo_promedio,
        "riesgo": riesgo,
        "valor_pipeline_usd": round(valor_total, 0),
        "valor_ponderado_usd": round(valor_ponderado, 0),
    }


def metricas_lider(db: Session, ahora: datetime | None = None,
                   es_demo: bool = False) -> dict:
    """Performance por vendedor para la vista del líder (admin). Ranking por
    valor ponderado del pipeline; incluye señales de riesgo y cierres.

    `es_demo` aísla el sandbox: True → solo vendedores/clientes/ops demo;
    False → solo los reales."""
    ahora = ahora or datetime.utcnow()
    sla_map = get_sla_map(db)
    en_consulta = {q.cliente_id for q in db.query(mv.VentasLiderConsulta.cliente_id)
                   .filter(mv.VentasLiderConsulta.estado == "pendiente")}
    vendedores = (db.query(mv.VentasVendedor)
                  .filter_by(activo=True, is_demo=es_demo).all())
    clientes = db.query(mv.VentasCliente).filter_by(is_demo=es_demo).all()
    ops = (db.query(mv.VentasOperacion)
           .filter(mv.VentasOperacion.estado == mv.OperacionEstado.cerrada,
                   mv.VentasOperacion.is_demo == es_demo).all())

    por_vend = {}
    for v in vendedores:
        por_vend[v.id] = {
            "vendedor_id": v.id, "nombre": v.nombre, "es_admin": v.es_admin,
            "activos": 0, "calientes": 0, "sin_proxima_accion": 0,
            "proxima_accion_vencida": 0, "sla_vencido": 0, "en_consulta_lider": 0,
            "cierres": 0, "comisiones_usd": 0.0,
            "valor_pipeline_usd": 0.0, "valor_ponderado_usd": 0.0,
        }

    for c in clientes:
        d = por_vend.get(c.vendedor_id)
        if not d:
            continue
        etapa = c.etapa or "nuevo_lead"
        if etapa in ESTADOS_ACTIVOS:
            d["activos"] += 1
            if (c.temperatura or "tibio") == "caliente":
                d["calientes"] += 1
            r = _riesgo_cliente(c, sla_map, ahora, en_consulta)
            for k in ("sin_proxima_accion", "proxima_accion_vencida",
                      "sla_vencido", "en_consulta_lider"):
                if r[k]:
                    d[k] += 1
            val = valor_cliente(c)
            d["valor_pipeline_usd"] += val
            d["valor_ponderado_usd"] += val * PROB_ETAPA.get(etapa, 0.0)

    for o in ops:
        d = por_vend.get(o.vendedor_id)
        if d:
            d["cierres"] += 1
            d["comisiones_usd"] += o.comision_monto_usd or 0.0

    filas = list(por_vend.values())
    for d in filas:
        d["valor_pipeline_usd"] = round(d["valor_pipeline_usd"], 0)
        d["valor_ponderado_usd"] = round(d["valor_ponderado_usd"], 0)
        d["comisiones_usd"] = round(d["comisiones_usd"], 2)
    filas.sort(key=lambda d: d["valor_ponderado_usd"], reverse=True)
    return {"vendedores": filas}
