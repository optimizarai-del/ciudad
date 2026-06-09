"""
Geocodificación dirección → barrio (Mod #5).

Flujo:
  1. Geocodificar la dirección a (lat, lng) con Nominatim (OpenStreetMap, gratis).
  2. Resolver a qué barrio pertenece ese punto con point-in-polygon contra los
     polígonos GeoJSON cargados en ventas_barrios.

Es best-effort: si Nominatim no responde (sin red, rate-limit) o no hay
polígonos cargados, devuelve lo que pudo. Nunca lanza excepción al caller.

Nominatim pide un User-Agent identificable y máximo 1 req/seg. Para el volumen
de este módulo (carga manual de propiedades) alcanza de sobra.
"""
import json
import urllib.parse
import urllib.request

from sqlalchemy.orm import Session

from app import models_ventas as mv

_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_UA = "CIUDAD-Ventas/1.0 (gestion inmobiliaria; contacto@optimizar-ia.com)"


def geocodificar(direccion: str, ciudad: str | None = None):
    """Devuelve (lat, lng) o (None, None) si no se pudo."""
    q = direccion if not ciudad else f"{direccion}, {ciudad}"
    params = urllib.parse.urlencode({
        "q": q, "format": "json", "limit": 1,
        "countrycodes": "ar",
    })
    try:
        req = urllib.request.Request(f"{_NOMINATIM}?{params}", headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:  # red caída, rate-limit, parse — degradamos a None
        print(f"[ventas_geo] geocodificar fallback: {e}")
    return None, None


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


def resolver(db: Session, direccion: str, ciudad: str | None = None):
    """Geocodifica + asigna barrio. Devuelve dict listo para GeocodeOut."""
    lat, lng = geocodificar(direccion, ciudad)
    barrio = barrio_de_punto(db, lat, lng) if lat is not None else None
    if lat is None:
        fuente = "sin_resultado"
    else:
        fuente = "nominatim"
    return {
        "lat": lat, "lng": lng,
        "barrio_id": barrio.id if barrio else None,
        "barrio_nombre": barrio.nombre if barrio else None,
        "fuente": fuente,
    }
