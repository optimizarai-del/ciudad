"""
Índices económicos en vivo.
Fuentes: INDEC (IPC), BCRA (ICL / UVA), DolarAPI (tipo de cambio).
"""
from datetime import date, timedelta
import httpx
from fastapi import APIRouter, Depends

from app.security import get_current_user

router = APIRouter(prefix="/api/indices", tags=["indices"])


@router.get("/")
async def get_indices(user=Depends(get_current_user)):
    resultado = {}
    hoy = date.today()
    desde = (hoy - timedelta(days=45)).strftime("%Y-%m-%d")
    hasta = hoy.strftime("%Y-%m-%d")

    async with httpx.AsyncClient(timeout=8.0, verify=False) as client:

        # ── IPC ── INDEC series API
        try:
            r = await client.get(
                "https://apis.datos.gob.ar/series/api/series/",
                params={
                    "ids": "148.3_INIVELG_DICI_M_26",
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
        except Exception as e:
            resultado["ipc"] = {"ok": False, "error": "INDEC no disponible"}

        # ── ICL ── BCRA variable 40
        try:
            r = await client.get(
                f"https://api.bcra.gob.ar/estadisticas/v2.0/DatosVariable/40/{desde}/{hasta}",
                headers={"Accept": "application/json"},
            )
            data = r.json()
            rows = data.get("results", [])
            if rows and len(rows) >= 2:
                ultimo = rows[-1]
                anterior = rows[-2]
                valor = float(ultimo.get("v", ultimo.get("valor", 0)))
                val_ant = float(anterior.get("v", anterior.get("valor", 0)))
                variacion = round((valor / val_ant - 1) * 100, 2) if val_ant else None
                resultado["icl"] = {
                    "valor": valor,
                    "variacion_mensual": variacion,
                    "fecha": ultimo.get("d", ultimo.get("fecha", "")),
                    "fuente": "BCRA",
                    "ok": True,
                }
            elif rows:
                ultimo = rows[-1]
                resultado["icl"] = {
                    "valor": float(ultimo.get("v", ultimo.get("valor", 0))),
                    "variacion_mensual": None,
                    "fecha": ultimo.get("d", ultimo.get("fecha", "")),
                    "fuente": "BCRA",
                    "ok": True,
                }
        except Exception:
            resultado["icl"] = {"ok": False, "error": "BCRA no disponible"}

        # ── UVA ── BCRA variable 4
        try:
            r = await client.get(
                f"https://api.bcra.gob.ar/estadisticas/v2.0/DatosVariable/4/{desde}/{hasta}",
                headers={"Accept": "application/json"},
            )
            data = r.json()
            rows = data.get("results", [])
            if rows:
                ultimo = rows[-1]
                resultado["uva"] = {
                    "valor": float(ultimo.get("v", ultimo.get("valor", 0))),
                    "fecha": ultimo.get("d", ultimo.get("fecha", "")),
                    "fuente": "BCRA",
                    "ok": True,
                }
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
