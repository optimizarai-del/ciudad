"""
Geocodificación dirección → (lat, lng) → barrio (Mod #5).

Flujo:
  1. Geocodificar la dirección a (lat, lng).
       - Si hay GOOGLE_MAPS_API_KEY → Google Maps Geocoding (preciso para AR).
       - Si no → Nominatim (OpenStreetMap, gratis, best-effort).
  2. Constraint por ZONA: toda propiedad que traemos de una búsqueda de zona
     (ej. Santa Rosa) DEBE quedar dentro de esa zona. Calculamos el centro de la
     zona y validamos que el pin caiga dentro de un radio razonable. Si un pin
     (venga de Tokko o del geocoder) cae fuera, lo corregimos al centro de la
     zona en vez de dejar la propiedad en otra ciudad (ej. Pilar).
  3. Resolver a qué barrio pertenece el punto (point-in-polygon).

Es best-effort: si el geocoder no responde, degradamos sin lanzar excepción.

Google pide una API key (variable de entorno GOOGLE_MAPS_API_KEY) con la
"Geocoding API" habilitada. Nominatim pide User-Agent identificable y máx
1 req/seg.
"""
import json
import math
import os
import urllib.parse
import urllib.request

from sqlalchemy.orm import Session

from app import models_ventas as mv

_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_UA = "CIUDAD-Ventas/1.0 (gestion inmobiliaria; contacto@optimizar-ia.com)"

_GOOGLE_GEOCODE = "https://maps.googleapis.com/maps/api/geocode/json"


def _google_key() -> str:
    return (os.getenv("GOOGLE_MAPS_API_KEY") or "").strip()


def tiene_google() -> bool:
    return bool(_google_key())


# ───────────────────────── parsing de zona ─────────────────────────

def parse_zona(zona_texto: str | None) -> tuple[str | None, str | None]:
    """De un texto de zona a (localidad, provincia).

    Acepta los formatos que devuelve Tokko/divisions:
      "La Pampa | Capital | Santa Rosa"          → ("Santa Rosa", "La Pampa")
      "Argentina | La Pampa | Capital | Santa Rosa" → ("Santa Rosa", "La Pampa")
      "Santa Rosa, La Pampa"                      → ("Santa Rosa", "La Pampa")
      "Santa Rosa"                                → ("Santa Rosa", None)
    """
    if not zona_texto:
        return None, None
    txt = zona_texto.strip()
    if "|" in txt:
        segs = [s.strip() for s in txt.split("|") if s.strip()]
        segs = [s for s in segs if s.lower() not in ("argentina",)]
        if not segs:
            return None, None
        localidad = segs[-1]
        provincia = segs[0] if len(segs) > 1 else None
        return localidad, provincia
    if "," in txt:
        segs = [s.strip() for s in txt.split(",") if s.strip()]
        segs = [s for s in segs if s.lower() not in ("argentina",)]
        if not segs:
            return None, None
        return segs[0], (segs[1] if len(segs) > 1 else None)
    return txt, None


def _query_zona(direccion: str | None, localidad: str | None,
                provincia: str | None) -> str:
    partes = [p for p in (direccion, localidad, provincia, "Argentina") if p]
    # Evitar duplicar la localidad si ya viene en la dirección
    vistos, limpio = set(), []
    for p in partes:
        k = p.strip().lower()
        if k in vistos:
            continue
        vistos.add(k)
        limpio.append(p.strip())
    return ", ".join(limpio)


# ───────────────────────── geocoders ─────────────────────────

def _geocodificar_google(direccion: str, localidad: str | None = None,
                         provincia: str | None = None) -> tuple:
    """(lat, lng, meta) con Google. meta trae localidad/provincia devueltas."""
    key = _google_key()
    if not key:
        return None, None, None
    components = "country:AR"
    if localidad:
        components += f"|locality:{localidad}"
    if provincia:
        components += f"|administrative_area:{provincia}"
    params = urllib.parse.urlencode({
        "address": _query_zona(direccion, localidad, provincia),
        "key": key, "region": "ar", "language": "es", "components": components,
    })
    try:
        req = urllib.request.Request(f"{_GOOGLE_GEOCODE}?{params}", headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        if data.get("status") != "OK" or not data.get("results"):
            return None, None, None
        res = data["results"][0]
        loc = res["geometry"]["location"]
        meta = {"formatted": res.get("formatted_address"),
                "partial": res.get("partial_match", False),
                "localidad": None, "provincia": None}
        for comp in res.get("address_components", []):
            tipos = comp.get("types", [])
            if "locality" in tipos:
                meta["localidad"] = comp.get("long_name")
            elif "administrative_area_level_1" in tipos:
                meta["provincia"] = comp.get("long_name")
        return float(loc["lat"]), float(loc["lng"]), meta
    except Exception as e:
        print(f"[ventas_geo] google fallback: {e}")
        return None, None, None


def _geocodificar_nominatim(direccion: str, localidad: str | None = None,
                            provincia: str | None = None) -> tuple:
    """(lat, lng) con Nominatim, acotado a Argentina."""
    q = _query_zona(direccion, localidad, provincia)
    params = urllib.parse.urlencode({
        "q": q, "format": "json", "limit": 1, "countrycodes": "ar",
        "addressdetails": 0,
    })
    try:
        req = urllib.request.Request(f"{_NOMINATIM}?{params}", headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"[ventas_geo] nominatim fallback: {e}")
    return None, None


def geocodificar(direccion: str, ciudad: str | None = None,
                 provincia: str | None = None) -> tuple:
    """(lat, lng) o (None, None). Google si hay key, Nominatim si no.

    `ciudad` puede venir como texto de zona ("La Pampa | Capital | Santa Rosa");
    se parsea a localidad/provincia para acotar la búsqueda.
    """
    localidad, prov2 = parse_zona(ciudad)
    provincia = provincia or prov2
    if _google_key():
        lat, lng, _ = _geocodificar_google(direccion, localidad, provincia)
        if lat is not None:
            return lat, lng
    return _geocodificar_nominatim(direccion, localidad, provincia)


# ───────────────────────── constraint por zona ─────────────────────────

def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def centro_de_zona(zona_texto: str | None) -> tuple:
    """Geocodifica la zona (localidad/provincia) para tener su centro de
    referencia. Devuelve (lat, lng) o (None, None)."""
    localidad, provincia = parse_zona(zona_texto)
    if not localidad and not provincia:
        return None, None
    if _google_key():
        lat, lng, _ = _geocodificar_google(None, localidad, provincia)
        if lat is not None:
            return lat, lng
    return _geocodificar_nominatim(None, localidad, provincia)


def dentro_de_zona(lat, lng, centro: tuple, radio_km: float = 40.0) -> bool:
    """True si el punto está dentro del radio del centro de la zona. Si no hay
    centro de referencia, no podemos validar → devolvemos True (no bloquear)."""
    if lat is None or lng is None:
        return False
    clat, clng = centro
    if clat is None or clng is None:
        return True
    return _haversine_km(lat, lng, clat, clng) <= radio_km


# ───────────────────────── barrio (point-in-polygon) ─────────────────────────

def _point_in_ring(lng, lat, ring):
    """Ray-casting sobre un anillo [[lng,lat], ...]."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and \
           (lng < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _point_in_geojson(lng, lat, geojson_str):
    """Soporta geometrías Polygon y MultiPolygon (y Feature que las envuelva)."""
    try:
        gj = json.loads(geojson_str)
    except Exception:
        return False
    geom = gj.get("geometry", gj)  # acepta Feature o geometry directa
    t = geom.get("type")
    coords = geom.get("coordinates", [])
    if t == "Polygon":
        polys = [coords]
    elif t == "MultiPolygon":
        polys = coords
    else:
        return False
    for poly in polys:
        if not poly:
            continue
        # poly[0] = anillo exterior; poly[1:] = huecos
        if _point_in_ring(lng, lat, poly[0]):
            if not any(_point_in_ring(lng, lat, hole) for hole in poly[1:]):
                return True
    return False


def barrio_de_punto(db: Session, lat: float, lng: float):
    """Devuelve el VentasBarrio que contiene el punto, o None."""
    if lat is None or lng is None:
        return None
    barrios = db.query(mv.VentasBarrio).filter(
        mv.VentasBarrio.poligono_geojson.isnot(None)
    ).all()
    for b in barrios:
        if _point_in_geojson(lng, lat, b.poligono_geojson):
            return b
    return None


def resolver(db: Session, direccion: str, ciudad: str | None = None,
             provincia: str | None = None):
    """Geocodifica + asigna barrio. Devuelve dict listo para GeocodeOut."""
    lat, lng = geocodificar(direccion, ciudad, provincia)
    barrio = barrio_de_punto(db, lat, lng) if lat is not None else None
    if lat is None:
        fuente = "sin_resultado"
    elif _google_key():
        fuente = "google"
    else:
        fuente = "nominatim"
    return {
        "lat": lat, "lng": lng,
        "barrio_id": barrio.id if barrio else None,
        "barrio_nombre": barrio.nombre if barrio else None,
        "fuente": fuente,
    }
