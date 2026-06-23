"""Adapter Argenprop (argenprop.com).

Argenprop sirve el listado en HTML server-side e incluye bloques JSON-LD
(`<script type="application/ld+json">`) por cada aviso. Parseamos esos
bloques (robusto a cambios de clases CSS) y caemos a un parseo por tarjeta
si no hay JSON-LD.

URL de listado:
  https://www.argenprop.com/casas-y-departamentos/venta/santa-rosa-la-pampa?pagina-N
"""
from __future__ import annotations

import json
import re

from ..base import (
    BaseAdapter, to_float, to_int, detectar_moneda, precio_display, map_tipo,
)

_LDJSON = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


class ArgenpropAdapter(BaseAdapter):
    fuente = "argenprop"
    nombre = "Argenprop"
    base_url = "https://www.argenprop.com"
    motor = "httpx"

    def listar_urls(self, ciudad: str, operacion: str, pagina: int) -> str:
        op = "venta" if operacion == "venta" else "alquiler"
        ciudad = (ciudad or "la-pampa").strip("/").lower().replace(" ", "-")
        url = f"{self.base_url}/casas-y-departamentos/{op}/{ciudad}"
        return url if pagina <= 1 else f"{url}?pagina-{pagina}"

    def parse_listado(self, html: str) -> list[dict]:
        filas: list[dict] = []
        for blob in _LDJSON.findall(html or ""):
            try:
                data = json.loads(blob.strip())
            except (json.JSONDecodeError, ValueError):
                continue
            items = data if isinstance(data, list) else [data]
            for it in items:
                if not isinstance(it, dict):
                    continue
                t = (it.get("@type") or "").lower()
                if t in ("product", "offer", "realestatelisting", "residence",
                         "apartment", "house", "singlefamilyresidence"):
                    filas.append(it)
        return filas

    def normalizar(self, raw: dict) -> dict:
        offers = raw.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        precio_raw = offers.get("price") or raw.get("price")
        moneda = (offers.get("priceCurrency")
                  or detectar_moneda(json.dumps(raw, ensure_ascii=False)))
        precio_num = to_float(precio_raw)

        addr = raw.get("address") or {}
        if isinstance(addr, dict):
            direccion = (addr.get("streetAddress") or raw.get("name") or "").strip()
            ubic = " ".join(filter(None, [
                addr.get("addressLocality"), addr.get("addressRegion"),
            ])).strip()
        else:
            direccion = (raw.get("name") or "").strip()
            ubic = str(addr).strip()

        geo = raw.get("geo") or {}
        url = raw.get("url") or ""
        if isinstance(url, list):
            url = url[0] if url else ""
        imagen = raw.get("image") or ""
        if isinstance(imagen, list):
            imagen = imagen[0] if imagen else ""

        ref = ""
        m = re.search(r"--(\d+)$", str(url))
        if m:
            ref = m.group(1)

        return {
            "referencia": ref or (str(url).rsplit("/", 1)[-1] if url else ""),
            "direccion": direccion or None,
            "ubicacion": ubic or None,
            "tipo": map_tipo(raw.get("name") or raw.get("@type") or ""),
            "operacion": None,  # lo fija el pipeline desde la config
            "precio_num": precio_num,
            "moneda": moneda,
            "precio_display": precio_display(precio_num, moneda),
            "m2_cubierta_num": to_float(raw.get("floorSize", {}).get("value")
                                        if isinstance(raw.get("floorSize"), dict) else None),
            "m2_total_num": None,
            "ambientes_num": to_int(raw.get("numberOfRooms")),
            "dormitorios_num": to_int(raw.get("numberOfBedrooms")),
            "banos_num": to_int(raw.get("numberOfBathroomsTotal")
                                or raw.get("numberOfBathrooms")),
            "lat": to_float(geo.get("latitude")) if isinstance(geo, dict) else None,
            "lng": to_float(geo.get("longitude")) if isinstance(geo, dict) else None,
            "detalles": (raw.get("description") or "").strip()[:1000] or None,
            "publicado_por": ((raw.get("seller") or {}).get("name")
                              if isinstance(raw.get("seller"), dict) else None),
            "ficha_url": str(url) or None,
            "foto": str(imagen) or None,
        }
