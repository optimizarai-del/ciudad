"""
Servicio de índices económicos en vivo.
Cachea las consultas en memoria para evitar pegarle a INDEC/BCRA en cada cálculo.
"""
import time
from datetime import date, timedelta
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
