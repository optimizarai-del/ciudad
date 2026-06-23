"""Adapter Zonaprop (zonaprop.com.ar).

Zonaprop está detrás de DataDome (anti-bot agresivo) y renderiza el listado
con JS, por eso el motor por defecto es Playwright. Los avisos vienen en un
bloque JSON embebido (`window.__PRELOADED_STATE__` / `postingsList`). Si en
algún momento sirven JSON-LD como Argenprop, el mismo parseo lo levanta.

URL de listado:
  https://www.zonaprop.com.ar/casas-departamentos-venta-santa-rosa-la-pampa-pagina-N.html
"""
from __future__ import annotations

import json
import re

from ..base import (
    BaseAdapter, to_float, to_int, detectar_moneda, precio_display, map_tipo,
)

_PRELOAD = re.compile(
    r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*;?\s*</script>",
    re.DOTALL,
)


def _walk_postings(obj):
    """Busca recursivamente listas de avisos dentro del estado precargado."""
    found = []
    if isinstance(obj, dict):
        if "postingId" in obj or "postingLocation" in obj:
            found.append(obj)
        for v in obj.values():
            found.extend(_walk_postings(v))
    elif isinstance(obj, list):
        for v in obj:
            found.extend(_walk_postings(v))
    return found


class ZonapropAdapter(BaseAdapter):
    fuente = "zonaprop"
    nombre = "Zonaprop"
    base_url = "https://www.zonaprop.com.ar"
    motor = "playwright"

    def listar_urls(self, ciudad: str, operacion: str, pagina: int) -> str:
        op = "venta" if operacion == "venta" else "alquiler"
        ciudad = (ciudad or "la-pampa").strip("/").lower().replace(" ", "-")
        slug = f"casas-departamentos-{op}-{ciudad}"
        if pagina > 1:
            slug += f"-pagina-{pagina}"
        return f"{self.base_url}/{slug}.html"

    def parse_listado(self, html: str) -> list[dict]:
        m = _PRELOAD.search(html or "")
        if not m:
            return []
        try:
            estado = json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            return []
        return _walk_postings(estado)

    def normalizar(self, raw: dict) -> dict:
        loc = raw.get("postingLocation") or {}
        addr = (loc.get("location") or {}) if isinstance(loc, dict) else {}
        coords = (loc.get("postingGeolocation") or {}).get("geolocation") or {} \
            if isinstance(loc, dict) else {}

        # Precio: estructura priceOperationTypes → prices[]
        precio_num, moneda = None, "USD"
        for opx in (raw.get("priceOperationTypes") or []):
            for pr in (opx.get("prices") or []):
                precio_num = to_float(pr.get("amount"))
                moneda = pr.get("currency") or moneda
                if precio_num:
                    break
            if precio_num:
                break

        feats = {f.get("label", "").lower(): f.get("value")
                 for f in (raw.get("mainFeatures") or {}).values()
                 if isinstance(f, dict)} if isinstance(raw.get("mainFeatures"), dict) else {}

        def feat(*keys):
            for k in keys:
                for label, val in feats.items():
                    if k in label:
                        return to_float(val)
            return None

        pid = str(raw.get("postingId") or "")
        url = raw.get("url") or raw.get("seoUrl") or ""
        if url and not url.startswith("http"):
            url = f"{self.base_url}/{url.lstrip('/')}"

        return {
            "referencia": pid,
            "direccion": (raw.get("postingTitle") or addr.get("address")
                          or addr.get("name") or "").strip() or None,
            "ubicacion": (addr.get("name") or loc.get("name") or "").strip() or None,
            "tipo": map_tipo(raw.get("realEstateType", {}).get("name")
                             if isinstance(raw.get("realEstateType"), dict)
                             else raw.get("postingTitle") or ""),
            "operacion": None,
            "precio_num": precio_num,
            "moneda": moneda,
            "precio_display": precio_display(precio_num, moneda),
            "m2_cubierta_num": feat("cubie"),
            "m2_total_num": feat("total", "terreno"),
            "ambientes_num": to_int(feat("ambiente")),
            "dormitorios_num": to_int(feat("dormitor")),
            "banos_num": to_int(feat("baño", "bano")),
            "lat": to_float(coords.get("latitude")),
            "lng": to_float(coords.get("longitude")),
            "detalles": (raw.get("description") or "").strip()[:1000] or None,
            "publicado_por": ((raw.get("publisher") or {}).get("name")
                              if isinstance(raw.get("publisher"), dict) else None),
            "ficha_url": url or None,
            "foto": next((p.get("url") for p in (raw.get("postingPictures") or [])
                          if isinstance(p, dict) and p.get("url")), None),
        }
