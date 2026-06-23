"""Pipeline de scraping: fetch → normaliza → dedup → detecta cambios → upsert.

Persiste en `ventas_scraping_propiedades` (espejo del patrón Red Tokko:
numérico para filtros + display para mostrar). La deduplicación cross-fuente
es por `ficha_url` (link canónico). La detección de cambios usa `content_hash`:
si el aviso ya existe y el hash no cambió, solo se toca `ultima_vez`; si cambió
(precio/m2/etc.) se actualizan los campos y se reactiva.

Las propiedades que dejan de aparecer en una corrida NO se borran: el caller
puede marcarlas `activa=False` (baja del portal) comparando contra el set de
URLs vistas.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models_ventas import VentasScrapingProp, VentasScrapingConfig
from . import get_adapter
from .base import content_hash


def get_config(db: Session, fuente: str) -> VentasScrapingConfig:
    cfg = (db.query(VentasScrapingConfig)
           .filter(VentasScrapingConfig.fuente == fuente).first())
    if not cfg:
        cfg = VentasScrapingConfig(fuente=fuente, activo=False)
        db.add(cfg)
        db.flush()
    return cfg


def sincronizar(db: Session, fuente: str, ciudad: str | None = None,
                operacion: str | None = None, max_paginas: int | None = None) -> dict:
    """Corre una pasada de scraping de `fuente` y upsertea en la tabla.

    Devuelve un resumen JSON-serializable.
    """
    adapter = get_adapter(fuente)
    cfg = get_config(db, fuente)
    ciudad = ciudad or cfg.ciudad or "la-pampa"
    operacion = operacion or cfg.operacion or "venta"
    max_paginas = max_paginas or cfg.max_paginas or 5

    crudos = adapter.fetch(ciudad, operacion, max_paginas)

    nuevas, actualizadas, sin_cambio, descartadas = 0, 0, 0, 0
    vistas: set[str] = set()

    for raw in crudos:
        try:
            norm = adapter.normalizar(raw)
        except Exception:
            descartadas += 1
            continue
        url = norm.get("ficha_url")
        if not url or not norm.get("precio_num"):
            descartadas += 1
            continue
        norm["operacion"] = operacion
        vistas.add(url)
        h = content_hash(norm)

        existente = (db.query(VentasScrapingProp)
                     .filter(VentasScrapingProp.ficha_url == url).first())
        if existente:
            if existente.content_hash == h and existente.activa:
                existente.ultima_vez = datetime.utcnow()
                sin_cambio += 1
            else:
                for k, v in norm.items():
                    setattr(existente, k, v)
                existente.content_hash = h
                existente.activa = True
                existente.ultima_vez = datetime.utcnow()
                actualizadas += 1
        else:
            prop = VentasScrapingProp(fuente=fuente, content_hash=h, activa=True,
                                      **norm)
            db.add(prop)
            nuevas += 1

    # Baja del portal: activas de esta fuente/operación que no aparecieron
    bajas = 0
    if vistas:
        previas = (db.query(VentasScrapingProp)
                   .filter(VentasScrapingProp.fuente == fuente,
                           VentasScrapingProp.operacion == operacion,
                           VentasScrapingProp.activa.is_(True)).all())
        for p in previas:
            if p.ficha_url not in vistas:
                p.activa = False
                bajas += 1

    resumen = {
        "ok": True, "fuente": fuente, "ciudad": ciudad, "operacion": operacion,
        "crudos": len(crudos), "nuevas": nuevas, "actualizadas": actualizadas,
        "sin_cambio": sin_cambio, "bajas": bajas, "descartadas": descartadas,
    }
    cfg.ultima_sync = datetime.utcnow()
    cfg.ultima_sync_resultado = json.dumps(resumen, ensure_ascii=False)
    db.flush()
    db.commit()
    return resumen
