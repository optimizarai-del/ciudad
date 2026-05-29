"""
Aplicación automática de ajustes de alquiler según el índice del contrato.

Cada contrato tiene:
  - monto_inicial          → valor base al firmar
  - indice_ajuste          → 'ipc' | 'icl' | 'fijo' | 'sin_ajuste'
  - periodicidad_meses     → 1 (mensual), 3 (trimestral), 6 (semestral), 12 (anual)
  - porcentaje_fijo        → sólo si indice='fijo'

El monto vigente en un momento dado es:
  monto_inicial × (1 + tasa_periodo) ^ cantidad_periodos_aplicados

Donde:
  - cantidad_periodos = floor(meses_transcurridos / periodicidad_meses)
  - tasa_periodo:
      * fijo  → porcentaje_fijo / 100
      * icl   → (1 + icl_mensual)^periodicidad − 1
      * ipc   → (1 + ipc_mensual)^periodicidad − 1
      * sin_ajuste → 0

Cada ajuste se registra como una fila en `ajustes_contrato` para tener
trazabilidad: fecha, %% aplicado, monto anterior, monto nuevo, índice usado.

Este servicio expone:
  - monto_vigente(contrato): devuelve el monto actual sin tocar la DB
  - aplicar_ajustes_pendientes(db, contrato): aplica los ajustes que falten
    desde el último registrado hasta hoy. Devuelve cuántos creó.
  - aplicar_ajustes_pendientes_bulk(db, contratos): para varios contratos.
"""
from __future__ import annotations

from datetime import date as _date
from typing import Iterable

from sqlalchemy.orm import Session

from app import models
from app.services.indices_service import get_tasas_cached_sync


def _meses_entre(desde: _date, hasta: _date) -> int:
    """Cantidad de meses completos entre dos fechas (hasta exclusivo del día)."""
    if not desde or not hasta or hasta < desde:
        return 0
    return (hasta.year - desde.year) * 12 + (hasta.month - desde.month)


def _indice_str(c: models.Contrato) -> str:
    v = c.indice_ajuste
    if v is None:
        return "sin_ajuste"
    return v.value if hasattr(v, "value") else str(v)


def _tasa_por_periodo(c: models.Contrato, periodicidad: int, tasas: dict) -> float:
    """Devuelve la tasa fraccional que se aplica en UN período de ajuste."""
    indice = _indice_str(c)
    if indice == "fijo":
        return (c.porcentaje_fijo or 0) / 100.0
    if indice == "icl":
        return (1 + tasas["icl_mensual"]) ** periodicidad - 1
    if indice == "ipc":
        return (1 + tasas["ipc_mensual"]) ** periodicidad - 1
    return 0.0


def monto_vigente(contrato: models.Contrato) -> float:
    """Devuelve el monto del último ajuste registrado, o el monto_inicial si no
    hay ajustes. NO consulta tasas vivas — solo lee lo guardado.
    Defensivo: si la tabla ajustes_contrato no existe (deploy parcial) o
    el lazy-load falla, retorna monto_inicial."""
    if not contrato:
        return 0.0
    try:
        ajustes = list(contrato.ajustes or [])
        if not ajustes:
            return float(contrato.monto_inicial or 0)
        ultimo = max(ajustes, key=lambda a: (a.fecha or _date.min, a.id))
        return float(ultimo.monto_nuevo or contrato.monto_inicial or 0)
    except Exception as e:
        print(f"[monto_vigente] {type(e).__name__}: {e} — fallback a monto_inicial")
        return float(contrato.monto_inicial or 0)


def aplicar_ajustes_pendientes(
    db: Session, contrato: models.Contrato, hoy: _date | None = None
) -> int:
    """Aplica todos los ajustes pendientes al contrato hasta `hoy`.

    Aplica los ajustes que correspondan según fecha de inicio del contrato
    y la periodicidad. Cada ajuste queda registrado en `ajustes_contrato`
    para trazabilidad. NO hace commit — el caller decide.

    Reglas:
      - Solo se aplica si contrato.estado == 'vigente'
      - Solo si indice_ajuste != 'sin_ajuste'
      - El primer ajuste ocurre a los `periodicidad_meses` del inicio
      - Si pasaron N períodos completos y solo M ajustes están registrados,
        se crean N − M ajustes (uno por cada período pendiente)

    Devuelve: cantidad de ajustes creados.
    """
    if not contrato:
        return 0
    estado = contrato.estado
    estado_v = estado.value if hasattr(estado, "value") else estado
    if estado_v != "vigente":
        return 0
    indice = _indice_str(contrato)
    if indice == "sin_ajuste":
        return 0
    if not contrato.fecha_inicio:
        return 0

    hoy = hoy or _date.today()
    periodicidad = int(contrato.periodicidad_meses or 0)
    if periodicidad <= 0:
        return 0

    meses = _meses_entre(contrato.fecha_inicio, hoy)
    periodos_esperados = meses // periodicidad
    if periodos_esperados <= 0:
        return 0

    ajustes_actuales = len(contrato.ajustes or [])
    if ajustes_actuales >= periodos_esperados:
        return 0

    faltan = periodos_esperados - ajustes_actuales

    # Tasas vivas (cache). Solo se piden una vez aunque haya varios ajustes.
    try:
        tasas = get_tasas_cached_sync()
    except Exception as e:
        print(f"[ajustes] no se pudieron obtener tasas vivas: {e}")
        return 0
    tasa_p = _tasa_por_periodo(contrato, periodicidad, tasas)
    if tasa_p == 0 and indice != "fijo":
        # No tiene sentido crear ajustes con 0% (probablemente las APIs fallaron)
        return 0

    # Crear los ajustes faltantes uno a uno, partiendo del último monto vigente
    monto_actual = monto_vigente(contrato)
    creados = 0
    for i in range(faltan):
        # Fecha del ajuste: inicio + (ajustes_actuales + i + 1) × periodicidad
        n_periodo = ajustes_actuales + i + 1
        # Calculamos el día con seguridad (clamp si el mes no tiene tantos días)
        offset_meses = n_periodo * periodicidad
        anio = contrato.fecha_inicio.year + (contrato.fecha_inicio.month - 1 + offset_meses) // 12
        mes = ((contrato.fecha_inicio.month - 1 + offset_meses) % 12) + 1
        try:
            fecha_ajuste = _date(anio, mes, contrato.fecha_inicio.day)
        except ValueError:
            # Día que no existe en el mes (ej 31 de febrero) → último día del mes
            from calendar import monthrange
            fecha_ajuste = _date(anio, mes, monthrange(anio, mes)[1])

        monto_nuevo = round(monto_actual * (1 + tasa_p), 2)
        db.add(models.AjusteContrato(
            contrato_id=contrato.id,
            fecha=fecha_ajuste,
            porcentaje=round(tasa_p * 100, 4),
            monto_anterior=monto_actual,
            monto_nuevo=monto_nuevo,
            indice_usado=indice,
        ))
        monto_actual = monto_nuevo
        creados += 1

    db.flush()
    return creados


def aplicar_ajustes_pendientes_bulk(
    db: Session, contratos: Iterable[models.Contrato], hoy: _date | None = None
) -> int:
    """Aplica ajustes pendientes a una lista de contratos. Devuelve el total
    de ajustes creados. No hace commit (lo deja al caller)."""
    total = 0
    for c in contratos:
        try:
            total += aplicar_ajustes_pendientes(db, c, hoy=hoy)
        except Exception as e:
            print(f"[ajustes_bulk] contrato {c.id}: {e}")
    return total
