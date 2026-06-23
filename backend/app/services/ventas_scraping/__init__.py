"""Módulo de scraping de webs inmobiliarias (Fase 4.1).

Arquitectura:
  base.py      → Adapter ABC + helpers de normalización (num + display)
  adapters/    → un módulo por sitio target (argenprop, zonaprop)
  pipeline.py  → normaliza + deduplica cross-fuente + detecta cambios + upsert
  queue.py     → cola Redis (RQ) + helpers de encolado
  tasks.py     → función-job que corre el worker
  worker.py    → entrypoint del worker (`rq worker`)

El catálogo de adapters disponibles se expone con `ADAPTERS`.
"""
from .adapters.argenprop import ArgenpropAdapter
from .adapters.zonaprop import ZonapropAdapter

ADAPTERS = {
    a.fuente: a for a in (ArgenpropAdapter(), ZonapropAdapter())
}


def get_adapter(fuente: str):
    a = ADAPTERS.get(fuente)
    if not a:
        raise ValueError(f"Fuente de scraping desconocida: {fuente}")
    return a


def fuentes_disponibles():
    return [a.info() for a in ADAPTERS.values()]
