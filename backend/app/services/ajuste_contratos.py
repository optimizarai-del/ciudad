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


def monto_para_mes(contrato: models.Contrato, mes: str | None) -> float:
    """Precio del alquiler que corresponde a un mes puntual (`mes` = 'YYYY-MM').

    A diferencia de `monto_vigente` (que devuelve SIEMPRE el último precio), acá
    el precio queda atado al período al que pertenece el mes: se toma el monto
    del último ajuste cuyo mes sea <= `mes`, o `monto_inicial` si a ese mes
    todavía no le aplicó ningún ajuste.

    Así, si en junio el alquiler valía 350 y en septiembre se ajustó a 400,
    consultar junio sigue devolviendo 350 aunque ya exista el ajuste de
    septiembre. Los meses pasados NO se mueven cuando llega un ajuste nuevo.

    Defensivo: ante cualquier fallo (tabla ausente, lazy-load roto) cae a
    monto_inicial. NO consulta tasas vivas — solo lee ajustes guardados."""
    if not contrato:
        return 0.0
    base = float(contrato.monto_inicial or 0)
    if not mes:
        return base
    # Normalizamos `mes` a (año, mes) numérico y comparamos por número, NO por
    # string: así '2026-7' (sin zero-pad) funciona igual que '2026-07'.
    try:
        _y, _m = str(mes).split("-")[:2]
        objetivo = (int(_y), int(_m))
    except Exception:
        return base
    try:
        aplicables = [
            a for a in (contrato.ajustes or [])
            if a.fecha and (a.fecha.year, a.fecha.month) <= objetivo
        ]
        if not aplicables:
            return base
        # Último ajuste aplicable con monto positivo. Si el más nuevo viniera en
        # 0/None (fila parcial/dato faltante), caemos al anterior real —no a
        # monto_inicial— para no bajar el alquiler por debajo de lo ya ajustado.
        for a in sorted(aplicables, key=lambda a: (a.fecha, a.id), reverse=True):
            if a.monto_nuevo:
                return float(a.monto_nuevo)
        return base
    except Exception as e:
        print(f"[monto_para_mes] {type(e).__name__}: {e} — fallback a monto_inicial")
        return base


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


def recalcular_ajustes(
    db: Session, contratos: Iterable[models.Contrato], dry_run: bool = True
) -> list[dict]:
    """Recalcula los ajustes YA EXISTENTES de cada contrato con la fórmula
    ACTUAL. El motor normal es idempotente: nunca reescribe un ajuste ya creado,
    así que si un ajuste se guardó con una versión anterior del cálculo, queda
    con el valor viejo. Esta función corrige eso.

    NO crea ni borra filas: recorre los ajustes existentes (respeta sus fechas)
    y recalcula monto_anterior / monto_nuevo / porcentaje encadenando desde
    `monto_inicial`. Con `dry_run=True` no persiste: solo devuelve el detalle
    de qué cambiaría. Con `dry_run=False` aplica los cambios (no hace commit;
    lo deja al caller).

    Importante: NO toca los pagos ya cobrados (esos conservan su monto_total
    histórico); solo corrige la tabla de ajustes, que es lo que define el precio
    vigente y el sugerido de los meses no cobrados.

    Devuelve una lista de dicts (uno por contrato con cambios) con el detalle
    período a período: viejo vs. correcto.
    """
    cambios: list[dict] = []
    for c in contratos:
        try:
            indice = _indice_str(c)
            if indice == "sin_ajuste":
                continue
            ajustes = sorted(
                [a for a in (c.ajustes or []) if a.fecha],
                key=lambda a: (a.fecha, a.id),
            )
            if not ajustes:
                continue
            per = int(c.periodicidad_meses or 0)
            if not c.fecha_inicio or per <= 0:
                # Sin fecha_inicio/periodicidad no podemos derivar los períodos
                # igual que la creación: no arriesgamos y saltamos el contrato.
                continue
            porcentaje_fijo = (c.porcentaje_fijo or 0) / 100.0
            monto = float(c.monto_inicial or 0)
            detalle: list[dict] = []
            corta = False
            for i, a in enumerate(ajustes):
                n = i + 1
                # Períodos derivados EXACTO como en la creación (aplicar_ajustes_
                # pendientes): así el recálculo = lo que el motor generaría hoy.
                fa = _fecha_periodo(c.fecha_inicio, n * per)
                pi = _fecha_periodo(c.fecha_inicio, (n - 1) * per)
                if indice == "fijo":
                    factor, fuente = 1 + porcentaje_fijo, "fijo"
                else:
                    factor, fuente = factor_acumulado(indice, pi, fa)
                if factor is None:
                    # Sin dato publicado para ese período: no tocamos esta fila
                    # ni las siguientes (dependen de su monto). Conservador.
                    detalle.append({"fecha": fa.isoformat(), "estado": "sin_dato",
                                    "motivo": fuente})
                    corta = True
                    break
                nuevo_anterior = round(monto, 2)
                nuevo_monto = round(monto * factor, 2)
                viejo_monto = float(a.monto_nuevo or 0)
                cambia = abs(nuevo_monto - viejo_monto) > 0.005
                detalle.append({
                    "fecha": fa.isoformat(),
                    "monto_nuevo_viejo": round(viejo_monto, 2),
                    "monto_nuevo_correcto": nuevo_monto,
                    "porcentaje_viejo": round(float(a.porcentaje or 0), 4),
                    "porcentaje_correcto": round((factor - 1) * 100, 4),
                    "cambia": cambia,
                })
                # Solo persistimos las filas que realmente cambian de monto, así
                # lo que se escribe coincide con lo que reporta `cambios`. El
                # encadenamiento (`monto`) se actualiza igual aunque no se escriba,
                # porque si no cambia, el monto guardado ya es igual a nuevo_monto.
                if not dry_run and cambia:
                    a.fecha = fa  # alinear a la fecha canónica del período
                    a.monto_anterior = nuevo_anterior
                    a.monto_nuevo = nuevo_monto
                    a.porcentaje = round((factor - 1) * 100, 4)
                    a.indice_usado = indice if indice != "fijo" else "fijo"
                monto = nuevo_monto
            if any(d.get("cambia") for d in detalle):
                cambios.append({
                    "contrato": c.codigo or f"#{c.id}",
                    "contrato_id": c.id,
                    "indice": indice,
                    "monto_inicial": float(c.monto_inicial or 0),
                    "monto_final_viejo": round(float(ajustes[-1].monto_nuevo or 0), 2),
                    "monto_final_correcto": round(monto, 2),
                    "incompleto": corta,
                    "detalle": detalle,
                })
        except Exception as e:
            print(f"[recalcular] contrato {getattr(c, 'id', '?')}: {type(e).__name__}: {e}")
    if not dry_run:
        db.flush()
    return cambios


# ════════════════════════════════════════════════════════════════════════════
#  Actualización DIARIA de índices + aplicación automática de ajustes
#
#  Se corre todos los días: refresca las series IPC (INDEC) e ICL (BCRA) y aplica
#  los ajustes que hayan quedado pendientes en cada contrato vigente. Así, en
#  cuanto el organismo publica el índice de un período, el ajuste se aplica solo
#  —sin depender de que alguien abra Cobranza—. Idempotente: no duplica ajustes.
# ════════════════════════════════════════════════════════════════════════════

# Latido en memoria: registra la última corrida del motor para poder verificar
# desde afuera que está vivo (endpoint /api/ajustes/estado). Se resetea al
# reiniciar el proceso, pero el loop corre apenas arranca, así que se repuebla
# en segundos. El histórico real de ajustes vive en la tabla ajustes_contrato.
_HEARTBEAT: dict = {
    "ultima_corrida": None,   # ISO datetime UTC de la última vez que corrió
    "ok": None,               # True si la última corrida no tuvo error
    "resumen": None,          # dict con el detalle de la última corrida
}


def estado_actualizacion() -> dict:
    """Devuelve una copia del latido de la última corrida del motor."""
    return dict(_HEARTBEAT)


def _registrar_corrida(resumen: dict) -> None:
    from datetime import datetime as _dt, timezone as _tz
    _HEARTBEAT["ultima_corrida"] = _dt.now(_tz.utc).isoformat()
    _HEARTBEAT["ok"] = "error" not in (resumen or {})
    _HEARTBEAT["resumen"] = resumen


def correr_actualizacion_diaria() -> dict:
    """Refresca los índices y aplica ajustes pendientes a todos los contratos
    vigentes. Crea y cierra su propia sesión. Devuelve un resumen."""
    from app.database import SessionLocal
    from app.services import indices_service

    estado_idx = {}
    try:
        estado_idx = indices_service.refrescar_series()
    except Exception as e:
        print(f"[ajustes-diarios] refrescar_series falló: {e}")

    db = SessionLocal()
    try:
        contratos = (db.query(models.Contrato)
                     .filter(models.Contrato.estado == "vigente").all())
        creados = aplicar_ajustes_pendientes_bulk(db, contratos)
        if creados:
            db.commit()
        resumen = {
            "indices": estado_idx,
            "contratos_vigentes": len(contratos),
            "ajustes_creados": creados,
            "fecha": _date.today().isoformat(),
        }
        print(f"[ajustes-diarios] {resumen}")
        _registrar_corrida(resumen)
        return resumen
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        print(f"[ajustes-diarios] error aplicando ajustes: {e}")
        resumen = {"indices": estado_idx, "error": str(e),
                   "fecha": _date.today().isoformat()}
        _registrar_corrida(resumen)
        return resumen
    finally:
        db.close()


async def loop_ajustes_diarios(intervalo_seg: int = 86400):
    """Loop de fondo: corre la actualización diaria cada `intervalo_seg` (24 h).
    Corre la parte bloqueante (httpx + DB) en un thread para no frenar el event
    loop. Se arranca desde el startup de main.py si AJUSTES_DIARIOS_ENABLED."""
    import asyncio
    while True:
        try:
            await asyncio.to_thread(correr_actualizacion_diaria)
        except Exception as e:
            print(f"[ajustes-diarios] ciclo falló: {e}")
        await asyncio.sleep(intervalo_seg)
