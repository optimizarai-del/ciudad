"""
Servicio de índices económicos en vivo.
Cachea las consultas en memoria para evitar pegarle a INDEC/BCRA en cada cálculo.
"""
import time
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import httpx

# Cache simple en memoria (se invalida cada 30 minutos).
_CACHE: dict = {"data": None, "ts": 0}
_TTL_SEG = 1800

# Fallbacks usados cuando INDEC/BCRA no responden o devuelven datos parciales.
IPC_MENSUAL_FALLBACK = 0.04
ICL_MENSUAL_FALLBACK = 0.05


async def _fetch_remoto() -> dict:
    """Llama a INDEC + BCRA y devuelve un dict con tasas mensuales reales o fallback."""
    hoy = date.today()
    desde = (hoy - timedelta(days=90)).strftime("%Y-%m-%d")
    hasta = hoy.strftime("%Y-%m-%d")

    resultado = {
        "ipc_mensual": IPC_MENSUAL_FALLBACK,
        "ipc_fuente": "fallback",
        "ipc_periodo": None,
        "ipc_ok": False,

        "icl_mensual": ICL_MENSUAL_FALLBACK,
        "icl_fuente": "fallback",
        "icl_fecha": None,
        "icl_ok": False,
    }

    async with httpx.AsyncClient(timeout=8.0, verify=False) as client:
        # IPC mensual nivel general nacional (INDEC vía datos.gob.ar)
        try:
            r = await client.get(
                "https://apis.datos.gob.ar/series/api/series/",
                params={
                    "ids": "148.3_INIVELNAL_DICI_M_26",
                    "limit": 6,
                    "sort": "desc",
                    "format": "json",
                },
            )
            data = r.json()
            series = data.get("data", [])
            if series and len(series) >= 2:
                actual = float(series[0][1])
                anterior = float(series[1][1])
                if anterior:
                    resultado["ipc_mensual"] = round(actual / anterior - 1, 6)
                    resultado["ipc_periodo"] = str(series[0][0])[:7]
                    resultado["ipc_fuente"] = "INDEC"
                    resultado["ipc_ok"] = True
        except Exception:
            pass

        # ICL — variación mensual variable 40 BCRA (API v4, datos en orden desc)
        try:
            r = await client.get(
                "https://api.bcra.gob.ar/estadisticas/v4.0/Monetarias/40",
                params={"desde": desde, "hasta": hasta},
                headers={"Accept": "application/json"},
            )
            data = r.json()
            res = data.get("results") or []
            rows = (res[0].get("detalle") if res else []) or []
            if rows and len(rows) >= 2:
                ultimo = float(rows[0].get("valor", 0))
                hace_30 = rows[30] if len(rows) > 30 else rows[-1]
                anterior = float(hace_30.get("valor", 0))
                if anterior:
                    resultado["icl_mensual"] = round(ultimo / anterior - 1, 6)
                    resultado["icl_fecha"] = rows[0].get("fecha", "")
                    resultado["icl_fuente"] = "BCRA"
                    resultado["icl_ok"] = True
        except Exception:
            pass

    return resultado


async def get_tasas_mensuales() -> dict:
    """Devuelve tasas mensuales actuales (con cache de 30 min)."""
    ahora = time.time()
    if _CACHE["data"] and (ahora - _CACHE["ts"]) < _TTL_SEG:
        return _CACHE["data"]
    data = await _fetch_remoto()
    _CACHE["data"] = data
    _CACHE["ts"] = ahora
    return data


def get_tasas_cached_sync() -> dict:
    """Versión sincrónica: devuelve cache si existe, sino fallback puro."""
    if _CACHE["data"]:
        return _CACHE["data"]
    return {
        "ipc_mensual": IPC_MENSUAL_FALLBACK,
        "ipc_fuente": "fallback",
        "ipc_ok": False,
        "icl_mensual": ICL_MENSUAL_FALLBACK,
        "icl_fuente": "fallback",
        "icl_ok": False,
    }


# ════════════════════════════════════════════════════════════════════════════
#  Índice HISTÓRICO (nivel) — para calcular ajustes reales entre dos fechas.
#
#  El ajuste correcto de un alquiler NO es "la tasa mensual de hoy compuesta N
#  veces": es la razón del índice entre la fecha de inicio del período y la fecha
#  del ajuste. Tanto INDEC (IPC, mensual) como BCRA (ICL, diario) publican el
#  NIVEL del índice, así que el factor exacto es  nivel(hasta) / nivel(desde).
#  Así se calcula legalmente un ajuste ICL.
# ════════════════════════════════════════════════════════════════════════════

# Cache de las series (nivel). TTL 6 h — el índice del pasado no cambia.
_SERIE_CACHE: dict = {"ipc": None, "ipc_ts": 0, "icl": None, "icl_ts": 0}
_SERIE_TTL = 6 * 3600


def _serie_ipc_sync() -> dict:
    """{ 'YYYY-MM': nivel_indice } del IPC nacional (INDEC). Cacheado."""
    ahora = time.time()
    if _SERIE_CACHE["ipc"] and (ahora - _SERIE_CACHE["ipc_ts"]) < _SERIE_TTL:
        return _SERIE_CACHE["ipc"]
    serie: dict = {}
    try:
        with httpx.Client(timeout=10.0, verify=False) as c:
            r = c.get("https://apis.datos.gob.ar/series/api/series/",
                      params={"ids": "148.3_INIVELNAL_DICI_M_26",
                              "limit": 240, "sort": "desc", "format": "json"})
            for fecha, valor in r.json().get("data", []):
                if valor is not None:
                    serie[str(fecha)[:7]] = float(valor)
    except Exception as e:
        print(f"[indices] serie IPC falló: {e}")
    if serie:
        _SERIE_CACHE["ipc"] = serie
        _SERIE_CACHE["ipc_ts"] = ahora
    return serie


def _serie_icl_sync(desde: date, hasta: date) -> list:
    """[(date, nivel), ...] ordenado asc del ICL diario (BCRA). Cacheado por
    rango amplio para servir cualquier par de fechas sin refetch."""
    ahora = time.time()
    cache = _SERIE_CACHE["icl"]
    if cache and (ahora - _SERIE_CACHE["icl_ts"]) < _SERIE_TTL:
        pares, c_desde, c_hasta = cache
        if c_desde <= desde and c_hasta >= hasta:
            return pares
    # Traer un rango generoso: desde 30 días antes del pedido más viejo hasta hoy.
    d0 = min(desde, hasta) - timedelta(days=30)
    d1 = date.today()
    pares: list = []
    try:
        with httpx.Client(timeout=12.0, verify=False) as c:
            r = c.get("https://api.bcra.gob.ar/estadisticas/v4.0/Monetarias/40",
                      params={"desde": d0.isoformat(), "hasta": d1.isoformat()},
                      headers={"Accept": "application/json"})
            res = r.json().get("results") or []
            rows = (res[0].get("detalle") if res else []) or []
            for row in rows:
                try:
                    f = date.fromisoformat(str(row.get("fecha"))[:10])
                    v = float(row.get("valor"))
                    pares.append((f, v))
                except Exception:
                    continue
    except Exception as e:
        print(f"[indices] serie ICL falló: {e}")
    pares.sort(key=lambda x: x[0])
    if pares:
        _SERIE_CACHE["icl"] = (pares, d0, d1)
        _SERIE_CACHE["icl_ts"] = ahora
    return pares


def _valor_icl_en(pares: list, objetivo: date):
    """Nivel ICL vigente en `objetivo`: el último dato con fecha <= objetivo."""
    val = None
    for f, v in pares:  # pares viene ordenado asc
        if f <= objetivo:
            val = v
        else:
            break
    return val


def factor_acumulado(indice: str, desde: date, hasta: date):
    """Factor de ajuste REAL entre dos fechas: nivel(hasta) / nivel(desde).

    - ICL: razón del índice diario del BCRA (método legal del ajuste), usando
      las fechas reales del contrato.
    - IPC: razón del nivel mensual del INDEC tomando los DATOS YA PUBLICADOS a
      la fecha del ajuste. INDEC publica cada IPC ~1 mes después del mes que
      mide (el IPC de junio sale ~13 de julio). Entonces un ajuste que rige en
      agosto usa los datos que SALIERON en mayo, junio y julio — que son los
      IPC de abril, mayo y junio → nivel(junio)/nivel(marzo). Así el ajuste
      aparece a tiempo (a inicio del mes) sin esperar dato del propio mes.
      En la práctica: correr ambos extremos DOS meses hacia atrás.

    Devuelve (factor, fuente) con factor > 0, o (None, motivo) si todavía no
    hay dato publicado para ese período. En ese caso el ajuste NO se crea — se
    reintenta cuando el organismo publique el dato. NUNCA usa valores de
    fallback: si no hay dato real, no ajusta.
    """
    indice = (indice or "").lower()
    if desde is None or hasta is None or hasta <= desde:
        return None, "rango_invalido"

    if indice == "ipc":
        serie = _serie_ipc_sync()
        if not serie:
            return None, "sin_datos_ipc"
        # Corremos ambos extremos DOS meses atrás para usar los IPC que YA
        # están publicados a la fecha del ajuste. Ajuste de agosto → usa los
        # datos salidos en mayo/junio/julio, que son los IPC de abril/mayo/junio
        # = nivel(junio)/nivel(marzo). (INDEC publica con ~1 mes de rezago.)
        d_ref = desde - relativedelta(months=2)
        h_ref = hasta - relativedelta(months=2)
        k_desde, k_hasta = d_ref.strftime("%Y-%m"), h_ref.strftime("%Y-%m")
        nivel_desde = serie.get(k_desde)
        nivel_hasta = serie.get(k_hasta)
        # El último mes de la ventana puede no estar publicado aún (INDEC tiene
        # ~1 mes de rezago). En ese caso NO ajustamos todavía: reintenta cuando
        # el organismo publique el dato.
        if nivel_desde is None or nivel_hasta is None or nivel_desde <= 0:
            return None, "ipc_no_publicado"
        return round(nivel_hasta / nivel_desde, 8), "INDEC"

    if indice == "icl":
        pares = _serie_icl_sync(desde, hasta)
        if not pares:
            return None, "sin_datos_icl"
        v_desde = _valor_icl_en(pares, desde)
        v_hasta = _valor_icl_en(pares, hasta)
        if not v_desde or not v_hasta:
            return None, "icl_no_publicado"
        return round(v_hasta / v_desde, 8), "BCRA"

    return None, "indice_no_soportado"


def refrescar_series() -> dict:
    """Fuerza el refetch de las series históricas IPC/ICL (invalida su cache).
    Pensado para la actualización diaria. Devuelve un resumen del estado."""
    _SERIE_CACHE["ipc_ts"] = 0
    _SERIE_CACHE["icl_ts"] = 0
    ipc = _serie_ipc_sync()
    hoy = date.today()
    icl = _serie_icl_sync(hoy - timedelta(days=400), hoy)
    return {
        "ipc_meses": len(ipc),
        "ipc_ultimo": (max(ipc.keys()) if ipc else None),
        "ipc_ok": bool(ipc),
        "icl_dias": len(icl),
        "icl_ultimo": (icl[-1][0].isoformat() if icl else None),
        "icl_ok": bool(icl),
    }
