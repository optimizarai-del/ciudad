"""Adapter base + helpers de normalización para scraping de webs.

Cada adapter (un sitio = un archivo bajo adapters/) implementa `fetch()` que
devuelve una lista de dicts CRUDOS (tal cual salen del HTML). El pipeline se
encarga de la normalización a través de `normalizar()`, que cada adapter
sobreescribe para mapear su estructura cruda al esquema canónico de
`VentasScrapingProp`.

Esquema canónico devuelto por `normalizar()`:
    referencia, direccion, ubicacion, tipo, operacion,
    precio_num, moneda, precio_display,
    m2_cubierta_num, m2_total_num, ambientes_num, dormitorios_num, banos_num,
    lat, lng, detalles, publicado_por, ficha_url, foto

Motor de fetch: por defecto httpx (liviano, deployable sin Chromium). Si el
sitio exige JS / anti-bot, el adapter puede declarar `motor="playwright"` y
usar `fetch_playwright()` — Playwright es OPCIONAL (no es dependencia dura del
backend); si no está instalado, el job falla con un mensaje claro en vez de
romper el import del módulo.
"""
from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod

import httpx

# Mapa de tipos del portal → enum interno VPropiedadTipo (tolerante por substring)
TIPO_MAP = {
    "casa": "casa", "ph": "departamento", "departamento": "departamento",
    "depto": "departamento", "dpto": "departamento", "monoambiente": "departamento",
    "terreno": "lote", "lote": "lote", "fondo de comercio": "local",
    "local": "local", "oficina": "oficina", "consultorio": "oficina",
    "galpon": "galpon", "galpón": "galpon", "deposito": "galpon",
    "depósito": "galpon", "campo": "campo", "chacra": "campo",
    "quinta": "campo", "cochera": "otro", "garage": "otro",
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


# ───────────────────────── parsers numéricos ─────────────────────────

def to_float(v):
    """'USD 150.000' / '120 m²' / '1.250,50' → float. None si no hay número."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) or None
    s = str(v)
    # Quitar todo menos dígitos, punto y coma
    s = re.sub(r"[^\d,.]", "", s)
    if not s:
        return None
    # Formato AR: miles con '.', decimal con ','  →  normalizar a float python
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    elif s.count(".") == 1:
        # Un único punto: en AR suele ser separador de miles ("150.000").
        # Solo lo tratamos como decimal si tiene 1-2 dígitos después.
        if len(s.split(".")[1]) == 3:
            s = s.replace(".", "")
    try:
        f = float(s)
        return f or None
    except ValueError:
        return None


def to_int(v):
    f = to_float(v)
    return int(f) if f is not None else None


def detectar_moneda(texto: str) -> str:
    t = (texto or "").upper()
    if "USD" in t or "U$S" in t or "DÓLAR" in t or "DOLAR" in t:
        return "USD"
    if "$" in t or "PESO" in t or "ARS" in t:
        return "ARS"
    return "USD"


def precio_display(num, moneda: str) -> str:
    if num is None:
        return "Consultar"
    miles = f"{int(num):,}".replace(",", ".")
    return f"{moneda} {miles}"


def map_tipo(texto: str) -> str:
    t = (texto or "").strip().lower()
    for k, v in TIPO_MAP.items():
        if k in t:
            return v
    return "otro"


def content_hash(norm: dict) -> str:
    """Hash de los campos que importan para detectar cambios reales."""
    base = "|".join(str(norm.get(k) or "") for k in (
        "precio_num", "moneda", "m2_cubierta_num", "dormitorios_num",
        "operacion", "direccion",
    ))
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


# ───────────────────────── Adapter ABC ─────────────────────────

class BaseAdapter(ABC):
    fuente: str = "base"
    nombre: str = "Base"
    base_url: str = ""
    motor: str = "httpx"          # "httpx" | "playwright"

    def info(self) -> dict:
        return {
            "id": self.fuente, "nombre": self.nombre,
            "base_url": self.base_url, "motor": self.motor,
        }

    @abstractmethod
    def listar_urls(self, ciudad: str, operacion: str, pagina: int) -> str:
        """Devuelve la URL de la página de listado nº `pagina`."""

    @abstractmethod
    def parse_listado(self, html: str) -> list[dict]:
        """Parsea el HTML de un listado → lista de dicts crudos."""

    @abstractmethod
    def normalizar(self, raw: dict) -> dict:
        """Dict crudo → esquema canónico de VentasScrapingProp."""

    # ── fetch (motor httpx por defecto) ──
    def fetch(self, ciudad: str, operacion: str, max_paginas: int) -> list[dict]:
        if self.motor == "playwright":
            return self.fetch_playwright(ciudad, operacion, max_paginas)
        crudos: list[dict] = []
        headers = {"User-Agent": UA, "Accept-Language": "es-AR,es;q=0.9"}
        with httpx.Client(timeout=25, headers=headers, follow_redirects=True) as c:
            for p in range(1, max_paginas + 1):
                url = self.listar_urls(ciudad, operacion, p)
                try:
                    r = c.get(url)
                    if r.status_code != 200:
                        break
                    filas = self.parse_listado(r.text)
                    if not filas:
                        break
                    crudos.extend(filas)
                except httpx.HTTPError:
                    break
        return crudos

    def fetch_playwright(self, ciudad: str, operacion: str, max_paginas: int) -> list[dict]:
        """Motor opcional para sitios con anti-bot/JS. Playwright NO es
        dependencia dura: si no está instalado, fallo explícito."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                f"El adapter '{self.fuente}' requiere Playwright "
                "(pip install playwright && playwright install chromium). "
                "No está instalado en este entorno."
            ) from e
        crudos: list[dict] = []
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(user_agent=UA, locale="es-AR")
            for p in range(1, max_paginas + 1):
                url = self.listar_urls(ciudad, operacion, p)
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(1500)
                    filas = self.parse_listado(page.content())
                    if not filas:
                        break
                    crudos.extend(filas)
                except Exception:
                    break
            browser.close()
        return crudos
