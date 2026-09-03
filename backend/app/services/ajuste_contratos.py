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

import math
from datetime import date as _date
from typing import Iterable

from sqlalchemy.orm import Session

from app import models
from app.services.indices_service import factor_acumulado

# Paso de redondeo del alquiler ajustado: se redondea HACIA ARRIBA al próximo
# múltiplo de este valor (ej. 34.657 -> 35.000). Así el alquiler queda en un
# número "prolijo" y se mantiene por todo el período hasta la próxima
# actualización. Configurable si en algún momento se quiere otro paso.
REDONDEO_PASO = 1000


def _redondear_arriba(monto, paso: int = REDONDEO_PASO):
    """Redondea `monto` hacia arriba al próximo múltiplo de `paso`.
    Defensivo: si no es un número válido lo devuelve tal cual; 0 o negativos
    se devuelven redondeados a 2 decimales sin tocar."""
    try:
        m = float(monto)
    except (TypeError, ValueError):
        return monto
    if m <= 0:
        return round(m, 2)
    if not paso or paso <= 0:
        return round(m, 2)
    return float(math.ceil(m / paso) * paso)


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
    # Fechas que YA tienen un ajuste (p. ej. un override manual): no las
    # duplicamos aunque el conteo por período las alcance.
    fechas_existentes = {a.fecha: a for a in (contrato.ajustes or []) if a.fecha}
    creados = 0
    for i in range(faltan):
        n_periodo = ajustes_actuales + i + 1
        fecha_ajuste = _fecha_periodo(contrato.fecha_inicio, n_periodo * periodicidad)
        periodo_inicio = _fecha_periodo(contrato.fecha_inicio, (n_periodo - 1) * periodicidad)

        # Si ya hay un ajuste en esa fecha (override manual u otro), no creamos
        # otro: encadenamos desde su valor y seguimos. Evita duplicados.
        if fecha_ajuste in fechas_existentes:
            monto_actual = float(fechas_existentes[fecha_ajuste].monto_nuevo or monto_actual)
            continue

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

        # Redondeo hacia arriba a $1.000 (número prolijo, se mantiene el período).
        monto_nuevo = _redondear_arriba(round(monto_actual * factor, 2))
        db.add(models.AjusteContrato(
            contrato_id=contrato.id,
            fecha=fecha_ajuste,
            porcentaje=round((monto_nuevo / monto_actual - 1) * 100, 4) if monto_actual else round((factor - 1) * 100, 4),
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
                # Ajuste MANUAL: se respeta tal cual —el usuario lo cargó a mano—.
                # No se recalcula ni se redondea, y la cadena sigue desde su valor.
                if getattr(a, "manual", False):
                    monto = float(a.monto_nuevo if a.monto_nuevo is not None else monto)
                    continue
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
                # Redondeo hacia arriba a $1.000 (igual que en la creación).
                nuevo_monto = _redondear_arriba(round(monto * factor, 2))
                viejo_monto = float(a.monto_nuevo or 0)
                cambia = abs(nuevo_monto - viejo_monto) > 0.005
                pct = round((nuevo_monto / nuevo_anterior - 1) * 100, 4) if nuevo_anterior else round((factor - 1) * 100, 4)
                detalle.append({
                    "fecha": fa.isoformat(),
                    "monto_nuevo_viejo": round(viejo_monto, 2),
                    "monto_nuevo_correcto": nuevo_monto,
                    "porcentaje_viejo": round(float(a.porcentaje or 0), 4),
                    "porcentaje_correcto": pct,
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
                    a.porcentaje = pct
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


def _boundary_de_periodo(contrato: models.Contrato, periodo: str):
    """Devuelve la fecha del ajuste (boundary) que GOBIERNA el mes `periodo`
    (YYYY-MM), o None si `periodo` es anterior al primer ajuste del contrato.
    Es el boundary con fecha <= último día del mes pedido."""
    if not contrato or not contrato.fecha_inicio:
        return None
    per = int(contrato.periodicidad_meses or 0)
    if per <= 0:
        return None
    try:
        y, m = [int(x) for x in str(periodo).split("-")[:2]]
    except Exception:
        return None
    from calendar import monthrange
    fin_periodo = _date(y, m, monthrange(y, m)[1])
    n = _meses_entre(contrato.fecha_inicio, fin_periodo) // per
    if n < 1:
        return None
    return _fecha_periodo(contrato.fecha_inicio, n * per)


def registrar_override_manual(
    db: Session, contrato: models.Contrato, periodo: str, monto_manual: float
) -> bool:
    """Registra/actualiza un ajuste MANUAL para el período que gobierna `periodo`.

    Se llama al COBRAR: si el usuario carga un monto de alquiler distinto al que
    sugiere el sistema, ese valor se ancla al boundary de ajuste vigente para ese
    mes y se marca `manual=True`. El motor no lo pisa: se mantiene hasta la próxima
    actualización del contrato (donde el índice se aplica SOBRE el valor manual).

    Devuelve True si registró/actualizó un override. No hace commit (lo deja al
    caller). Defensivo: ante cualquier problema devuelve False sin romper el cobro.
    """
    try:
        indice = _indice_str(contrato)
        if indice == "sin_ajuste":
            return False
        monto_manual = round(float(monto_manual or 0), 2)
        if monto_manual <= 0:
            return False
        boundary = _boundary_de_periodo(contrato, periodo)
        if boundary is None:
            return False  # período anterior al primer ajuste: no hay qué overridear
        # Solo se registra el override si el mes que se cobra ES el mes de
        # actualización del contrato (el boundary). Un cambio manual en un mes
        # intermedio del período no redefine el precio del período.
        try:
            y, m = [int(x) for x in str(periodo).split("-")[:2]]
        except Exception:
            return False
        if not (boundary.year == y and boundary.month == m):
            return False
        # Valor previo (informativo, para monto_anterior/porcentaje).
        prev_ajustes = sorted(
            [a for a in (contrato.ajustes or []) if a.fecha and a.fecha < boundary],
            key=lambda a: (a.fecha, a.id),
        )
        prev_val = (float(prev_ajustes[-1].monto_nuevo) if prev_ajustes
                    else float(contrato.monto_inicial or 0))
        pct = round((monto_manual / prev_val - 1) * 100, 4) if prev_val else 0.0
        existente = next((a for a in (contrato.ajustes or []) if a.fecha == boundary), None)
        if existente:
            existente.manual = True
            existente.monto_anterior = prev_val
            existente.monto_nuevo = monto_manual
            existente.porcentaje = pct
            existente.indice_usado = "manual"
        else:
            db.add(models.AjusteContrato(
                contrato_id=contrato.id,
                fecha=boundary,
                porcentaje=pct,
                monto_anterior=prev_val,
                monto_nuevo=monto_manual,
                indice_usado="manual",
                manual=True,
            ))
        db.flush()
        return True
    except Exception as e:
        print(f"[override_manual] contrato {getattr(contrato, 'id', '?')}: {type(e).__name__}: {e}")
        return False


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
        # 1) Crear los ajustes que falten (períodos ya cumplidos con índice
        #    publicado que todavía no tienen su fila de ajuste).
        creados = aplicar_ajustes_pendientes_bulk(db, contratos)
        # 2) AUTO-SANADO: recalcular los ajustes YA EXISTENTES con la fórmula
        #    actual. El motor es idempotente y nunca reescribe un ajuste creado,
        #    así que si alguno se guardó con una versión anterior del cálculo
        #    quedaría con el valor viejo para siempre. Este paso lo corrige solo,
        #    todos los días —sin intervención manual—. No toca pagos ya cobrados
        #    (esos conservan su monto histórico); solo corrige la tabla de
        #    ajustes, que define el precio vigente y el sugerido de lo no cobrado.
        corregidos = 0
        try:
            cambios = recalcular_ajustes(db, contratos, dry_run=False)
            corregidos = len(cambios)
        except Exception as e:
            print(f"[ajustes-diarios] auto-sanado (recalcular) falló: {e}")
        if creados or corregidos:
            db.commit()
        resumen = {
            "indices": estado_idx,
            "contratos_vigentes": len(contratos),
            "ajustes_creados": creados,
            "ajustes_corregidos": corregidos,
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
