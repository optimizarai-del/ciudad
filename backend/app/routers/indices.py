"""
Índices económicos en vivo.
Fuentes: INDEC (IPC vía datos.gob.ar), BCRA v4 (ICL / UVA), DolarAPI (tipo de cambio).
"""
from datetime import date, timedelta
import httpx
from fastapi import APIRouter, Depends

from app.security import get_current_user

router = APIRouter(prefix="/api/indices", tags=["indices"])


# IDs vigentes (actualizados a 2026-05).
INDEC_IPC_SERIE = "148.3_INIVELNAL_DICI_M_26"  # IPC nivel general nacional, mensual
BCRA_VAR_ICL = 40
BCRA_VAR_UVA = 31


def _detalle_bcra(payload: dict) -> list[dict]:
    """En la API v4 los datos vienen en results[0].detalle, ordenados por fecha desc."""
    res = payload.get("results") or []
    if not res:
        return []
    primero = res[0] if isinstance(res, list) else res
    return primero.get("detalle") or []


@router.get("/")
async def get_indices(user=Depends(get_current_user)):
    resultado = {}
    hoy = date.today()
    desde = (hoy - timedelta(days=90)).strftime("%Y-%m-%d")
    hasta = hoy.strftime("%Y-%m-%d")

    async with httpx.AsyncClient(timeout=8.0, verify=False) as client:

        # ── IPC ── INDEC (datos.gob.ar)
        try:
            r = await client.get(
                "https://apis.datos.gob.ar/series/api/series/",
                params={
                    "ids": INDEC_IPC_SERIE,
                    "limit": 6,
                    "sort": "desc",
                    "format": "json",
                },
            )
            data = r.json()
            series = data.get("data", [])
            if series and len(series) >= 2:
                valor_actual = float(series[0][1])
                valor_anterior = float(series[1][1])
                variacion = round((valor_actual / valor_anterior - 1) * 100, 2)
                resultado["ipc"] = {
                    "valor": valor_actual,
                    "variacion_mensual": variacion,
                    "periodo": str(series[0][0])[:7],
                    "fuente": "INDEC",
                    "ok": True,
                }
            elif series:
                resultado["ipc"] = {
                    "valor": float(series[0][1]),
                    "variacion_mensual": None,
                    "periodo": str(series[0][0])[:7],
                    "fuente": "INDEC",
                    "ok": True,
                }
            else:
                resultado["ipc"] = {"ok": False, "error": "INDEC sin datos"}
        except Exception:
            resultado["ipc"] = {"ok": False, "error": "INDEC no disponible"}

        # ── ICL ── BCRA v4 variable 40 (datos diarios, orden desc)
        try:
            r = await client.get(
                f"https://api.bcra.gob.ar/estadisticas/v4.0/Monetarias/{BCRA_VAR_ICL}",
                params={"desde": desde, "hasta": hasta},
                headers={"Accept": "application/json"},
            )
            rows = _detalle_bcra(r.json())
            if rows:
                ultimo = rows[0]
                # buscar valor de ~30 días antes para variación mensual
                hace_30 = rows[30] if len(rows) > 30 else rows[-1]
                valor = float(ultimo.get("valor", 0))
                val_ant = float(hace_30.get("valor", 0))
                variacion = round((valor / val_ant - 1) * 100, 2) if val_ant else None
                resultado["icl"] = {
                    "valor": valor,
                    "variacion_mensual": variacion,
                    "fecha": ultimo.get("fecha", ""),
                    "fuente": "BCRA",
                    "ok": True,
                }
            else:
                resultado["icl"] = {"ok": False, "error": "BCRA sin datos"}
        except Exception:
            resultado["icl"] = {"ok": False, "error": "BCRA no disponible"}

        # ── UVA ── BCRA v4 variable 31
        try:
            r = await client.get(
                f"https://api.bcra.gob.ar/estadisticas/v4.0/Monetarias/{BCRA_VAR_UVA}",
                params={"desde": desde, "hasta": hasta},
                headers={"Accept": "application/json"},
            )
            rows = _detalle_bcra(r.json())
            if rows:
                ultimo = rows[0]
                hace_30 = rows[30] if len(rows) > 30 else rows[-1]
                valor = float(ultimo.get("valor", 0))
                val_ant = float(hace_30.get("valor", 0))
                variacion = round((valor / val_ant - 1) * 100, 2) if val_ant else None
                resultado["uva"] = {
                    "valor": valor,
                    "variacion_mensual": variacion,
                    "fecha": ultimo.get("fecha", ""),
                    "fuente": "BCRA",
                    "ok": True,
                }
            else:
                resultado["uva"] = {"ok": False, "error": "BCRA sin datos"}
        except Exception:
            resultado["uva"] = {"ok": False, "error": "BCRA no disponible"}

        # ── Dólar oficial ── DolarAPI
        try:
            r = await client.get("https://dolarapi.com/v1/dolares/oficial", timeout=5.0)
            d = r.json()
            resultado["dolar_oficial"] = {
                "compra": d.get("compra"),
                "venta": d.get("venta"),
                "fecha": str(d.get("fechaActualizacion", ""))[:10],
                "fuente": "DolarAPI",
                "ok": True,
            }
        except Exception:
            resultado["dolar_oficial"] = {"ok": False, "error": "No disponible"}

        # ── Dólar blue ── DolarAPI
        try:
            r = await client.get("https://dolarapi.com/v1/dolares/blue", timeout=5.0)
            d = r.json()
            resultado["dolar_blue"] = {
                "compra": d.get("compra"),
                "venta": d.get("venta"),
                "fecha": str(d.get("fechaActualizacion", ""))[:10],
                "fuente": "DolarAPI",
                "ok": True,
            }
        except Exception:
            resultado["dolar_blue"] = {"ok": False, "error": "No disponible"}

    return resultado
