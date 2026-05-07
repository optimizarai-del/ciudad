"""
Indices economicos en vivo.
Fuentes: INDEC (IPC nivel general), BCRA v4.0 (ICL / UVA), DolarAPI (tipo de cambio).
"""
import httpx
from fastapi import APIRouter, Depends

from app.security import get_current_user

router = APIRouter(prefix="/api/indices", tags=["indices"])


async def _bcra_variable(client, var_id):
    """Llama a BCRA v4.0 y devuelve la lista de detalle ordenada por fecha asc."""
    r = await client.get(
        f"https://api.bcra.gob.ar/estadisticas/v4.0/Monetarias/{var_id}",
        headers={"Accept": "application/json"},
    )
    data = r.json()
    results = data.get("results", [])
    if not results:
        return []
    detalle = results[0].get("detalle", []) or []
    detalle.sort(key=lambda x: x.get("fecha", ""))
    return detalle


@router.get("/")
async def get_indices(user=Depends(get_current_user)):
    resultado = {}

    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:

        # ── IPC nivel general ── INDEC (serie 101.1_I2NG_2016_M_22)
        try:
            r = await client.get(
                "https://apis.datos.gob.ar/series/api/series/",
                params={
                    "ids": "101.1_I2NG_2016_M_22",
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

        # ── ICL ── BCRA v4.0 variable 40
        try:
            detalle = await _bcra_variable(client, 40)
            if detalle and len(detalle) >= 2:
                ultimo = detalle[-1]
                anterior = detalle[-2]
                valor = float(ultimo.get("valor", 0))
                val_ant = float(anterior.get("valor", 0))
                variacion = round((valor / val_ant - 1) * 100, 2) if val_ant else None
                resultado["icl"] = {
                    "valor": valor,
                    "variacion_mensual": variacion,
                    "fecha": ultimo.get("fecha", ""),
                    "fuente": "BCRA",
                    "ok": True,
                }
            elif detalle:
                ultimo = detalle[-1]
                resultado["icl"] = {
                    "valor": float(ultimo.get("valor", 0)),
                    "variacion_mensual": None,
                    "fecha": ultimo.get("fecha", ""),
                    "fuente": "BCRA",
                    "ok": True,
                }
            else:
                resultado["icl"] = {"ok": False, "error": "BCRA sin datos"}
        except Exception:
            resultado["icl"] = {"ok": False, "error": "BCRA no disponible"}

        # ── UVA ── BCRA v4.0 variable 31 (UVA - en pesos)
        # 31 = UVA, 32 = UVI. Variable 4 anterior fue dada de baja en v4.
        try:
            detalle = await _bcra_variable(client, 31)
            if detalle and len(detalle) >= 2:
                ultimo = detalle[-1]
                anterior = detalle[-2]
                valor = float(ultimo.get("valor", 0))
                val_ant = float(anterior.get("valor", 0))
                variacion = round((valor / val_ant - 1) * 100, 2) if val_ant else None
                resultado["uva"] = {
                    "valor": valor,
                    "variacion_mensual": variacion,
                    "fecha": ultimo.get("fecha", ""),
                    "fuente": "BCRA",
                    "ok": True,
                }
            elif detalle:
                ultimo = detalle[-1]
                resultado["uva"] = {
                    "valor": float(ultimo.get("valor", 0)),
                    "variacion_mensual": None,
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
