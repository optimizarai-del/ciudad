"""Vigencia de contratos según sus fechas.

Un contrato puede cargarse con fecha de inicio en el futuro: en ese caso no
debe "correr" ni figurar en la cobranza/dashboard hasta que llegue su fecha de
inicio, y debe dejar de figurar una vez pasada su fecha de fin. Estas funciones
centralizan ese criterio para que cobranza, resumen y dashboard lo apliquen
igual.

`estado` (borrador/vigente/vencido/...) sigue siendo la intención del operador;
la vigencia por fecha es una capa temporal que se cruza con ese estado.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional


def _mes_bounds(mes: str) -> tuple[date, date]:
    """Primer y último día del mes 'YYYY-MM' (acepta también 'YYYY-M')."""
    y_str, m_str = str(mes).split("-")[:2]
    y, m = int(y_str), int(m_str)
    primero = date(y, m, 1)
    # Primer día del mes siguiente menos un día = último día del mes.
    if m == 12:
        sig = date(y + 1, 1, 1)
    else:
        sig = date(y, m + 1, 1)
    return primero, sig - timedelta(days=1)


def activo_en_mes(fecha_inicio: Optional[date], fecha_fin: Optional[date], mes: Optional[str]) -> bool:
    """¿El contrato está vigente en algún día del mes 'YYYY-MM'?

    Regla: se solapa el rango [fecha_inicio, fecha_fin] con el mes.
      - Empieza después del último día del mes  → todavía no arrancó → False.
      - Terminó antes del primer día del mes     → ya finalizó       → False.
    Si faltan fechas, se considera activo (comportamiento legacy: no romper
    contratos viejos sin fechas cargadas).
    """
    if not mes:
        return True
    try:
        primero, ultimo = _mes_bounds(mes)
    except Exception:
        return True
    if fecha_inicio and fecha_inicio > ultimo:
        return False
    if fecha_fin and fecha_fin < primero:
        return False
    return True


def vigencia_actual(fecha_inicio: Optional[date], fecha_fin: Optional[date],
                    hoy: Optional[date] = None) -> str:
    """Etiqueta temporal del contrato respecto de HOY, para el badge de la UI:
      - 'por_comenzar' → la fecha de inicio es futura.
      - 'finalizado'   → la fecha de fin ya pasó.
      - 'en_curso'     → hoy cae dentro del rango.
      - 'sin_fechas'   → no hay fechas cargadas.
    """
    hoy = hoy or date.today()
    if not fecha_inicio and not fecha_fin:
        return "sin_fechas"
    if fecha_inicio and hoy < fecha_inicio:
        return "por_comenzar"
    if fecha_fin and hoy > fecha_fin:
        return "finalizado"
    return "en_curso"
