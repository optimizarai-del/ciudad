"""Cola Redis (RQ) para los jobs de scraping (Fase 4.1).

Redis es OPCIONAL: si `REDIS_URL` no está seteada o redis/rq no están
instalados, `cola_disponible()` devuelve False y el router cae a ejecución
síncrona (útil en local/dev). En producción se levanta un worker aparte con
`python -m app.services.ventas_scraping.worker`.
"""
from __future__ import annotations

import os
from functools import lru_cache

REDIS_URL = os.getenv("REDIS_URL", "").strip()
QUEUE_NAME = os.getenv("SCRAPING_QUEUE", "scraping")


@lru_cache(maxsize=1)
def _conn():
    if not REDIS_URL:
        return None
    try:
        from redis import Redis
        c = Redis.from_url(REDIS_URL)
        c.ping()
        return c
    except Exception:
        return None


def cola_disponible() -> bool:
    return _conn() is not None


def get_queue():
    conn = _conn()
    if conn is None:
        return None
    try:
        from rq import Queue
        return Queue(QUEUE_NAME, connection=conn,
                     default_timeout=int(os.getenv("SCRAPING_JOB_TIMEOUT", "900")))
    except ImportError:
        return None


def encolar(fuente: str, ciudad: str, operacion: str, max_paginas: int,
            job_db_id: int) -> str | None:
    """Encola el job de scraping. Devuelve el rq_job_id o None si no hay cola."""
    q = get_queue()
    if q is None:
        return None
    from .tasks import correr_scraping_job
    job = q.enqueue(correr_scraping_job, fuente, ciudad, operacion,
                    max_paginas, job_db_id)
    return job.id


def estado_job(rq_job_id: str) -> str | None:
    conn = _conn()
    if conn is None or not rq_job_id:
        return None
    try:
        from rq.job import Job
        return Job.fetch(rq_job_id, connection=conn).get_status()
    except Exception:
        return None
