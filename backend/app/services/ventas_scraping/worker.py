"""Entrypoint del worker RQ de scraping (Fase 4.1).

Uso (proceso separado del backend, en EasyPanel un servicio aparte):

    python -m app.services.ventas_scraping.worker

Requiere REDIS_URL seteada y un Redis accesible. Escucha la cola definida en
SCRAPING_QUEUE (default "scraping").
"""
from __future__ import annotations

import os
import sys


def main():
    from .queue import _conn, QUEUE_NAME
    conn = _conn()
    if conn is None:
        print("[scraping-worker] REDIS_URL no configurada o Redis inaccesible. "
              "Abortando.", file=sys.stderr)
        sys.exit(1)
    from rq import Queue, Worker
    queue = Queue(QUEUE_NAME, connection=conn)
    worker = Worker([queue], connection=conn)
    print(f"[scraping-worker] escuchando cola '{QUEUE_NAME}' "
          f"en {os.getenv('REDIS_URL')}")
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
