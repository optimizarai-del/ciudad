"""
Aplicación automática de ajustes de alquiler según el índice del contrato.

Cada contrato tiene:
  - monto_inicial          → valor base al firmar
  - indice_ajuste          → 'ipc' | 'icl' | 'fijo' | 'sin_ajuste'
  - periodicidad_meses     → 1 (mensual), 3 (trimestral), 6 (semestral), 12 (anual)
  - porcentaje_fijo        → sólo si indice='fijo'

Cada período de ajuste usa el ÍNDICE REAL entre la fecha de inicio del período
y la fecha del ajuste (no la tasa mensual de hoy compuesta, que era incorrecta):

  factor_periodo = nivel_indice(fecha_ajuste) / nivel_indice(inicio_del_periodo)
  monto_nuevo    = monto_anterior × factor_periodo

Donde:
  - cantidad_periodos = floor(meses_transcurridos / periodicidad_meses)
  - factor_periodo:
      * fijo  → 1 + porcentaje_fijo / 100
      * icl   → ICL(fecha_ajuste) / ICL(inicio)   [nivel diario BCRA; método legal]
      * ipc   → IPC(mes_ajuste) / IPC(mes_inicio)  [nivel mensual INDEC]
      * sin_ajuste → no ajusta

Si el índice del período todavía NO está publicado (ej. IPC del mes en curso),
el ajuste no se crea y se reintenta más adelante. Nunca se usan valores de
fallback: mejor no ajustar que ajustar con datos inventados.

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
from app.services.indices_service import factor_acumulado


def _fecha_periodo(inicio: _date, offset_meses: int) -> _date:
    """inicio + offset_meses, con clamp del día si el mes no tiene tantos días."""
    anio = inicio.year + (inicio.month - 1 + offset_meses) // 12
    mes = ((inicio.month - 1 + offset_meses) % 12) + 1
    try:
        return _date(anio, mes, inicio.day)
    except ValueError:
        from calendar import monthrange
        return _date(anio, mes, monthrange(anio, mes)[1])


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

    # Crear los ajustes faltantes uno a uno, partiendo del último monto vigente.
    # Cada ajuste usa el ÍNDICE REAL del período: razón nivel(fecha_ajuste) /
    # nivel(inicio_del_período). NO se usa la tasa de hoy compuesta ni valores de
    # fallback: si el índice del período todavía no está publicado, se corta y se
    # reintenta la próxima vez (mejor no ajustar que ajustar con datos inventados).
    porcentaje_fijo = (contrato.porcentaje_fijo or 0) / 100.0
    monto_actual = monto_vigente(contrato)
    creados = 0
    for i in range(faltan):
        n_periodo = ajustes_actuales + i + 1
        fecha_ajuste = _fecha_periodo(contrato.fecha_inicio, n_periodo * periodicidad)
        periodo_inicio = _fecha_periodo(contrato.fecha_inicio, (n_periodo - 1) * periodicidad)

        if indice == "fijo":
            factor = 1 + porcentaje_fijo
            fuente = "fijo"
        else:
            factor, fuente = factor_acumulado(indice, periodo_inicio, fecha_ajuste)
            if factor is None:
                # El índice de este período aún no está disponible (o falló la
                # API). Cortamos: no persistimos ajustes con datos que no son
                # reales. Los períodos siguientes dependen de éste.
                print(f"[ajustes] contrato {contrato.id}: periodo {n_periodo} "
                      f"({periodo_inicio} a {fecha_ajuste}) sin dato {indice} ({fuente}); "
                      f"se reintentara. Creados hasta ahora: {creados}")
                break

        monto_nuevo = round(monto_actual * factor, 2)
        db.add(models.AjusteContrato(
            contrato_id=contrato.id,
            fecha=fecha_ajuste,
            porcentaje=round((factor - 1) * 100, 4),
            monto_anterior=monto_actual,
            monto_nuevo=monto_nuevo,
            indice_usado=(indice if indice != "fijo" else "fijo"),
        ))
        monto_actual = monto_nuevo
        creados += 1

    if creados:
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
