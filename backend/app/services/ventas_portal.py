"""
Importador de portales inmobiliarios públicos (vía scraping).

La API de Tokko sólo expone el inventario de la propia cuenta y la "Red Tokko"
no es accesible por API (confirmado por soporte). Para traer lo publicado en una
ciudad por CUALQUIER inmobiliaria, leemos un portal público.

Implementación inicial: **Argenprop** (anti-bot liviano, HTML estable con
atributos `data-*` por aviso). Cada propiedad entra al catálogo con
`fuente=scraping`, deduplicada por su URL pública. Las coordenadas no vienen en
el listado, así que quedan para el geocoding (botón "Ubicar pendientes" del mapa
o el backfill de /propiedades/geocodificar-faltantes), reutilizando ventas_geo.

Nota legal/ToS: los portales prohíben el scraping en sus términos. Es una zona
gris; el uso queda a criterio del negocio. Por eso el sync es manual (no un cron)
y respeta un ritmo prudente.
"""
import html
import re
import unicodedata
import urllib.request

from sqlalchemy.orm import Session

from app import models_ventas as mv

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
_BASE = "https://www.argenprop.com"


def _slug(texto: str) -> str:
    """'Santa Rosa' → 'santa-rosa' (sin acentos, minúsculas, guiones)."""
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t.strip().lower())
    return t.strip("-")


# Tipo de Argenprop (del slug del href: '/casa-en-venta-...') → nuestro enum.
_TIPO_MAP = {
    "casa": mv.VPropiedadTipo.casa,
    "departamento": mv.VPropiedadTipo.departamento,
    "ph": mv.VPropiedadTipo.departamento,
    "terreno": mv.VPropiedadTipo.lote,
    "lote": mv.VPropiedadTipo.lote,
    "local": mv.VPropiedadTipo.local,
    "oficina": mv.VPropiedadTipo.oficina,
    "consultorio": mv.VPropiedadTipo.oficina,
    "galpon": mv.VPropiedadTipo.galpon,
    "deposito": mv.VPropiedadTipo.galpon,
    "campo": mv.VPropiedadTipo.campo,
    "quinta": mv.VPropiedadTipo.campo,
    "chacra": mv.VPropiedadTipo.campo,
}


def _limpiar(s: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", s or "")).strip()


def _fetch(slug: str, pagina: int) -> str:
    url = f"{_BASE}/inmuebles/venta/{slug}"
    if pagina > 1:
        url += f"-pagina-{pagina}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "ignore")


def _parse_features(bloque: str) -> dict:
    """De los <span> de card__main-features saca m², dormitorios, baños."""
    m = re.search(r'card__main-features">(.*?)</ul>', bloque, re.S)
    out = {"superficie_m2": None, "dormitorios": None, "banos": None}
    if not m:
        return out
    for span in re.findall(r"<span[^>]*>([^<]+)</span>", m.group(1)):
        txt = _limpiar(span).lower()
        if "m²" in txt or "m2" in txt or "mts" in txt:
            num = re.search(r"([\d\.]+)", txt.replace(".", ""))
            if num and out["superficie_m2"] is None:
                try: out["superficie_m2"] = float(num.group(1))
                except ValueError: pass
        elif "dormitorio" in txt or "ambiente" in txt:
            num = re.search(r"(\d+)", txt)
            if num and out["dormitorios"] is None:
                out["dormitorios"] = int(num.group(1))
        elif "baño" in txt:
            num = re.search(r"(\d+)", txt)
            if num and out["banos"] is None:
                out["banos"] = int(num.group(1))
    return out


def _parse(html_doc: str, ciudad: str) -> list:
    """Convierte el HTML de un listado de Argenprop en kwargs de VentasPropiedad."""
    props = []
    for bloque in re.split(r'<div class="listing__item', html_doc)[1:]:
        href = re.search(r'href="(/[a-z]+-en-venta[^"]*?-\d+)"', bloque)
        if not href:
            continue
        link = _BASE + href.group(1)
        tipo_slug = re.match(r"/([a-z]+)-en-venta", href.group(1))
        tipo = _TIPO_MAP.get(tipo_slug.group(1) if tipo_slug else "", mv.VPropiedadTipo.otro)

        moneda = re.search(r'data-moneda="([A-Z]+)"', bloque)
        precio_m = re.search(r'data-precio="(\d+)"', bloque)
        precio = None
        if precio_m and int(precio_m.group(1)) > 0 and (moneda and moneda.group(1) == "USD"):
            precio = float(precio_m.group(1))

        direccion = re.search(r'class="card__address"[^>]*>([^<]+)', bloque)
        titulo = re.search(r"<h2[^>]*>([^<]+)</h2>", bloque)
        feats = _parse_features(bloque)
        # Varios hrefs traen "-N-ambientes-"; lo usamos como dormitorios si el
        # bloque de features no lo trajo.
        if feats["dormitorios"] is None:
            amb = re.search(r"-(\d+)-ambientes", href.group(1))
            if amb:
                feats["dormitorios"] = int(amb.group(1))

        props.append({
            "titulo": _limpiar(titulo.group(1)) if titulo else None,
            "tipo": tipo,
            "estado": mv.VPropiedadEstado.disponible,
            "fuente": mv.VPropiedadFuente.scraping,
            "direccion": _limpiar(direccion.group(1)) if direccion else None,
            "ciudad": ciudad,
            "precio_usd": precio,
            "link_externo": link,
            "inmobiliaria": "Argenprop",
            **feats,
        })
    return props


def sincronizar(db: Session, ciudad: str, provincia: str = "La Pampa",
                max_paginas: int = 5) -> dict:
    """Importa de Argenprop las propiedades en venta de una ciudad. Pagina hasta
    `max_paginas` o hasta que una página no traiga avisos. Dedup por URL."""
    slug = f"{_slug(ciudad)}-{_slug(provincia)}" if provincia else _slug(ciudad)
    nuevas = actualizadas = 0
    vistas = 0
    try:
        for pagina in range(1, max_paginas + 1):
            doc = _fetch(slug, pagina)
            lote = _parse(doc, ciudad)
            if not lote:
                break
            vistas += len(lote)
            for norm in lote:
                link = norm.get("link_externo")
                existente = None
                if link:
                    existente = (db.query(mv.VentasPropiedad)
                                 .filter_by(link_externo=link,
                                            fuente=mv.VPropiedadFuente.scraping).first())
                if existente:
                    for k, val in norm.items():
                        setattr(existente, k, val)
                    actualizadas += 1
                else:
                    db.add(mv.VentasPropiedad(**norm))
                    nuevas += 1
            db.flush()
    except Exception as e:
        return {"ok": False, "motivo": f"Error al leer Argenprop: {e}",
                "nuevas": nuevas, "actualizadas": actualizadas}

    return {"ok": True, "portal": "argenprop", "ciudad": ciudad,
            "nuevas": nuevas, "actualizadas": actualizadas, "vistas": vistas}
