"""Red Tokko EN VIVO (Fase 2+ / mejora de zona).

Trae propiedades de la RED Tokko que la API oficial no expone, vía login web +
el endpoint interno `pre_search` (lo mismo que hace el panel de Tokko). A
diferencia del CLI, esto corre dentro del backend para que el vendedor dispare
la búsqueda por zona desde la plataforma.

Dos operaciones:
  - resolver_zonas(pattern)  → candidatos de ubicación para DESAMBIGUAR
    (devuelve la ruta completa "Provincia | Depto | Localidad" para elegir).
  - buscar_en_vivo(loc_id, loc_type, ...) → trae la zona elegida, normaliza
    (display + numérico), geocodifica el pin si falta, y upsertea en
    `red_tokko_propiedades` para que se pueda importar al catálogo.

La sesión web se cachea a nivel módulo (TTL) para no re-loguear en cada búsqueda.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta

import httpx
from sqlalchemy import text, bindparam
from sqlalchemy.orm import Session

from app.database import IS_POSTGRES
from app.services import ventas_geo

LOGIN_URL = "https://www.tokkobroker.com/go/"
LOGIN_POST = "https://www.tokkobroker.com/login/?next=/home"
PRESEARCH = "https://www.tokkobroker.com/properties/pre_search/"
DIVISIONS = "https://www.tokkobroker.com/locations_api/v1/divisions/"

OP_ID = {"venta": 1, "alquiler": 2, "alquiler_temporal": 3}
_LOC_TYPE = {"D": "division", "C": "city", "S": "state", "Z": "zone", "N": "neighborhood"}

# El servicio opera SOLO en Argentina: la desambiguación nunca debe ofrecer
# ubicaciones de otros países. Tokko devuelve rutas inconsistentes: las
# extranjeras a veces encabezan con el país ("México | …", "Estados Unidos | …")
# y a veces con un estado/provincia extranjera ("Yucatán | Mérida | …"). Las
# argentinas encabezan con "Argentina | …" o con una provincia argentina, o
# tienen la provincia en algún segmento. Regla robusta:
#   ES argentina  ⇔  (el primer segmento NO es un país extranjero)
#                     Y (encabeza con "Argentina" o algún segmento es provincia AR)
# Así "Entre Rios | Uruguay | …" (Uruguay = depto de Entre Ríos) queda incluida,
# y "España | Cordoba | …" o "Yucatán | …" quedan excluidas.
_PAISES_EXTRANJEROS = {
    "mexico", "estados unidos", "usa", "ee uu", "eeuu", "uruguay", "chile",
    "paraguay", "bolivia", "brasil", "brazil", "colombia", "peru", "ecuador",
    "venezuela", "espana", "panama", "costa rica", "republica dominicana",
    "guatemala", "honduras", "el salvador", "nicaragua", "cuba", "puerto rico",
    "canada", "francia", "italia", "portugal",
}
_PROVINCIAS_AR = {
    "buenos aires", "ciudad autonoma de buenos aires", "caba", "capital federal",
    "catamarca", "chaco", "chubut", "cordoba", "corrientes", "entre rios",
    "formosa", "jujuy", "la pampa", "la rioja", "mendoza", "misiones", "neuquen",
    "rio negro", "salta", "san juan", "san luis", "santa cruz", "santa fe",
    "santiago del estero", "tierra del fuego", "tucuman",
}


def _norm(s: str) -> str:
    """minúsculas, sin acentos, sin espacios extra — para comparar segmentos."""
    s = (s or "").strip().lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s)


def _es_argentina(ruta: str) -> bool:
    if not ruta:
        return False
    segs = [_norm(s) for s in ruta.split("|")]
    if not segs:
        return False
    if segs[0] in _PAISES_EXTRANJEROS:
        return False
    if segs[0] == "argentina":
        return True
    return any(s in _PROVINCIAS_AR for s in segs)

# Sesión web cacheada (login es caro: la reusamos por un rato).
_SESSION: dict = {"client": None, "expira": None}
_SESSION_TTL = timedelta(minutes=15)


# ───────────────────────── login / sesión ─────────────────────────

def _creds() -> tuple[str, str]:
    u = os.getenv("TOKKO_USER", "").strip()
    p = os.getenv("TOKKO_PASS", "").strip()
    if not u or not p:
        raise RuntimeError(
            "Faltan credenciales web de Tokko. Configurá TOKKO_USER y TOKKO_PASS "
            "en el .env del backend.")
    return u, p


def _login() -> httpx.Client:
    u, p = _creds()
    c = httpx.Client(verify=False, timeout=40.0, follow_redirects=True,
                     headers={"User-Agent": "Mozilla/5.0"})
    r = c.get(LOGIN_URL)
    m = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', r.text)
    token = m.group(1) if m else c.cookies.get("csrftoken", "")
    c.post(LOGIN_POST, data={"csrfmiddlewaretoken": token, "username": u,
                             "password": p}, headers={"Referer": LOGIN_URL})
    if "sessionid" not in c.cookies:
        raise RuntimeError("No se pudo iniciar sesión en Tokko. Revisá TOKKO_USER / TOKKO_PASS.")
    return c


def _client(forzar: bool = False) -> httpx.Client:
    now = datetime.utcnow()
    if (not forzar and _SESSION["client"] is not None
            and _SESSION["expira"] and now < _SESSION["expira"]):
        return _SESSION["client"]
    c = _login()
    _SESSION["client"] = c
    _SESSION["expira"] = now + _SESSION_TTL
    return c


def _invalidar_sesion():
    _SESSION["client"] = None
    _SESSION["expira"] = None


def _get_json(url: str, params: dict, intentos: int = 3):
    """GET autenticado que devuelve JSON. Si la sesión quedó inválida (Tokko
    responde HTML/login o no-JSON), re-loguea y reintenta. Robustez clave: la
    sesión web a veces queda rechazada y hay que rehacerla."""
    ultimo_err = None
    for i in range(intentos):
        c = _client(forzar=(i > 0))
        try:
            r = c.get(url, params=params)
            ctype = r.headers.get("content-type", "")
            # Respuesta válida sólo si es JSON real
            if r.status_code == 200 and "json" in ctype.lower():
                return r.json()
            # status 200 pero HTML (login expirado) o error → re-login y reintento
            ultimo_err = f"http={r.status_code} ctype={ctype}"
            _invalidar_sesion()
            time.sleep(0.5)
        except Exception as e:
            ultimo_err = str(e)
            _invalidar_sesion()
            time.sleep(0.5)
    raise RuntimeError(f"Tokko no respondió JSON tras {intentos} intentos ({ultimo_err}).")


def _divisions(pattern: str) -> list:
    try:
        return _get_json(DIVISIONS, {"format": "json", "pattern": pattern}).get("results", [])
    except RuntimeError:
        return []


# ───────────────────────── resolución de zona ─────────────────────────

def resolver_zonas(pattern: str, limit: int = 10, solo_argentina: bool = True) -> list[dict]:
    """Devuelve candidatos de ubicación para que el usuario ELIJA el correcto.
    Por defecto SOLO Argentina (el servicio no opera en el exterior).
    Cada candidato: {loc_id, loc_type, valor, nombre, ruta}."""
    if not pattern or len(pattern.strip()) < 2:
        return []
    # Pedimos de más porque vamos a descartar las extranjeras y recortar después.
    results = _divisions(pattern.strip())
    out = []
    for x in results:
        ruta = x.get("name")
        if solo_argentina and not _es_argentina(ruta):
            continue
        val = x.get("value", "")
        pref, _, num = val.partition("-")
        if not num:
            continue
        out.append({
            "loc_id": num,
            "loc_type": _LOC_TYPE.get(pref, "division"),
            "valor": val,                      # "D-37004"
            "nombre": x.get("text") or ruta,
            "ruta": ruta,                      # "La Pampa | Capital | Santa Rosa"
        })
        if len(out) >= limit:
            break
    return out


# ───────────────────────── búsqueda en vivo ─────────────────────────

def _data(operacion, precio_min, precio_max, loc_id, loc_type) -> dict:
    return {
        "filters": [["network_share__in", "op", [50, 30]]],
        "only_available": "checked", "only_reserved": "undefined",
        "only_to_be_cotized": "undefined", "only_not_available": "undefined",
        "with_tags": [], "without_tags": [], "with_custom_tags": [],
        "with_or_custom_tags": [], "without_custom_tags": [],
        "listing_edition_review": "undefined", "division_filters": [],
        "state_filters": [], "current_localization_id": str(loc_id or "0"),
        "current_localization_type": loc_type or "", "network": [3],
        "exclude_my_properties": False,
        "price_from": str(int(precio_min)) if precio_min else "0",
        "price_to": str(int(precio_max)) if precio_max else "9999999999",
        "operation_types": [OP_ID.get((operacion or "").lower())] if operacion else [],
        "property_types": [], "currency": "USD", "bounding_box": [],
    }


def _num(s):
    if s is None:
        return None
    d = re.sub(r"[^\d]", "", str(s))
    return int(d) if d else None


def _float(s):
    if s is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(s))
    return float(m.group(0)) if m else None


def _moneda(*vals):
    for v in vals:
        if v and "USD" in str(v):
            return "USD"
        if v and ("$" in str(v) or "ARS" in str(v)):
            return "ARS"
    return "USD"


def _normalizar(p: dict) -> dict:
    def g(*keys):
        for k in keys:
            v = p.get(k)
            if v not in (None, "", "USD 0", "0", "$ 0"):
                return v
        return None
    precio_disp = g("OP1USD", "OP2USD", "OP3USD")
    lat = _float(p.get("geo_lat"))
    lng = _float(p.get("geo_long") or p.get("geo_lng"))
    # Tokko a veces manda 0/0 → lo tratamos como faltante
    if lat == 0:
        lat = None
    if lng == 0:
        lng = None
    return {
        "referencia": p.get("reference") or str(p.get("id") or ""),
        "tokko_id": p.get("id"),
        "direccion": p.get("address") or p.get("fake_address") or p.get("location"),
        "ubicacion": p.get("location"),
        "tipo": p.get("type"),
        "precio_display": precio_disp,
        "precio_num": _num(precio_disp),
        "moneda": _moneda(precio_disp),
        "m2_cubierta_num": _num(p.get("roofed_surface")),
        "m2_total_num": _num(p.get("surface") or p.get("total_surface")),
        "ambientes_num": _num(p.get("rooms")),
        "dormitorios_num": _num(p.get("suits")),
        "banos_num": _num(p.get("bathroom_amount")),
        "lat": lat, "lng": lng,
        "detalles": None,
        "publicado_por": p.get("company_name") or p.get("network_company_code"),
        "ficha_url": p.get("info_url"),
        "foto": p.get("cover_table") or p.get("cover"),
    }


_RED_COLS = ["referencia", "tokko_id", "direccion", "ubicacion", "tipo", "operacion",
             "precio_num", "moneda", "precio_display", "m2_cubierta_num", "m2_total_num",
             "ambientes_num", "dormitorios_num", "banos_num", "lat", "lng", "detalles",
             "publicado_por", "ficha_url", "foto", "zona_consulta", "actualizado_at"]


def _upsert(db: Session, rows: list[dict]):
    """Upsert portable (Postgres ON CONFLICT / SQLite INSERT OR REPLACE-like)
    por `referencia`. La tabla red_tokko_propiedades no es ORM."""
    if not rows:
        return 0
    cols = ", ".join(_RED_COLS)
    ph = ", ".join(f":{c}" for c in _RED_COLS)
    if IS_POSTGRES:
        setters = ", ".join(f"{c}=excluded.{c}" for c in _RED_COLS if c != "referencia")
        sql = text(f"insert into red_tokko_propiedades ({cols}) values ({ph}) "
                   f"on conflict (referencia) do update set {setters}")
        for r in rows:
            db.execute(sql, r)
    else:
        # SQLite: borro la referencia previa e inserto (idempotente).
        delsql = text("delete from red_tokko_propiedades where referencia = :referencia")
        inssql = text(f"insert into red_tokko_propiedades ({cols}) values ({ph})")
        for r in rows:
            db.execute(delsql, {"referencia": r["referencia"]})
            db.execute(inssql, r)
    db.commit()
    return len(rows)


def buscar_en_vivo(db: Session, loc_id: str, loc_type: str, operacion: str = "venta",
                   precio_min=None, precio_max=None, limit: int = 60,
                   zona_nombre: str = "", geocodificar: bool = True,
                   max_geocode: int = 20) -> dict:
    """Trae la zona elegida de la red Tokko, normaliza, geocodifica el pin si
    falta, y upsertea en red_tokko_propiedades. Devuelve las filas."""
    data = _data(operacion, precio_min, precio_max, loc_id, loc_type)
    juntadas, total_red = [], None
    for page in range(40):
        try:
            body = _get_json(PRESEARCH, {"order_by": "-id", "page": page,
                                         "data": json.dumps(data)})
        except RuntimeError:
            break
        if not isinstance(body, list) or not body:
            break
        if total_red is None:
            try:
                total_red = body[0][0].get("total")
            except Exception:
                total_red = None
        filas = [x for x in body[1:] if isinstance(x, dict)]
        if not filas:
            break
        for p in filas:
            juntadas.append(_normalizar(p))
            if len(juntadas) >= limit:
                break
        if len(juntadas) >= limit:
            break
        time.sleep(0.25)

    # Localización precisa + constraint por ZONA: ninguna propiedad de una
    # búsqueda de (ej.) Santa Rosa puede terminar con el pin en otra ciudad.
    #   1. Validamos el pin que trae Tokko: si cae fuera de la zona, lo tiramos.
    #   2. Geocodificamos por dirección (Google si hay key; si no, Nominatim),
    #      acotado a la zona buscada.
    #   3. Si aún no hay pin válido, lo "clavamos" al centro de la zona: queda
    #      en la ciudad correcta (aproximado) en lugar de en otra provincia.
    RADIO_KM = 45.0
    centro = ventas_geo.centro_de_zona(zona_nombre) if zona_nombre else (None, None)
    usa_google = ventas_geo.tiene_google()
    geocodificadas, corregidas = 0, 0
    if geocodificar:
        for r in juntadas:
            pin_ok = (r.get("lat") is not None and r.get("lng") is not None
                      and ventas_geo.dentro_de_zona(r["lat"], r["lng"], centro, RADIO_KM))
            if not pin_ok:
                r["lat"], r["lng"] = None, None
                if r.get("direccion") and geocodificadas < max_geocode:
                    lat, lng = ventas_geo.geocodificar(
                        r["direccion"], zona_nombre or r.get("ubicacion"))
                    geocodificadas += 1
                    if lat is not None and ventas_geo.dentro_de_zona(lat, lng, centro, RADIO_KM):
                        r["lat"], r["lng"], pin_ok = lat, lng, True
                    if not usa_google:
                        time.sleep(1.0)  # Nominatim: 1 req/seg
            # Fallback: no hay pin confiable → centro de la zona (ciudad correcta)
            if not pin_ok and centro[0] is not None:
                r["lat"], r["lng"] = centro
                r["geo_aproximada"] = True
                corregidas += 1

    # Preparar filas para upsert
    ahora = datetime.utcnow().isoformat()
    for r in juntadas:
        r["operacion"] = operacion
        r["zona_consulta"] = zona_nombre or loc_id
        r["actualizado_at"] = ahora
        for c2 in _RED_COLS:
            r.setdefault(c2, None)
    _upsert(db, juntadas)

    # Marcar ya_importada
    from app import models_ventas as mv
    urls = [r["ficha_url"] for r in juntadas if r.get("ficha_url")]
    importadas = set()
    if urls:
        importadas = {x[0] for x in db.query(mv.VentasPropiedad.link_externo)
                      .filter(mv.VentasPropiedad.link_externo.in_(urls))}
    for r in juntadas:
        r["ya_importada"] = r.get("ficha_url") in importadas

    return {"total_red": total_red, "trajo": len(juntadas),
            "geocodificadas": geocodificadas, "corregidas_a_zona": corregidas,
            "geocoder": "google" if usa_google else "nominatim",
            "propiedades": juntadas}
