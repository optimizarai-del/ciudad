"""Función-job que ejecuta el worker RQ (Fase 4.1).

Importante: el worker corre en un proceso aparte, sin la sesión de FastAPI,
así que abre su propia DB session vía SessionLocal y actualiza el registro
`VentasScrapingJob` con el progreso/resultado.
"""
from __future__ import annotations

import json
from datetime import datetime

from app.database import SessionLocal
from app.models_ventas import VentasScrapingJob, ScrapingJobEstado
from .pipeline import sincronizar


def correr_scraping_job(fuente: str, ciudad: str, operacion: str,
                        max_paginas: int, job_db_id: int) -> dict:
    db = SessionLocal()
    try:
        job = db.get(VentasScrapingJob, job_db_id) if job_db_id else None
        if job:
            job.estado = ScrapingJobEstado.corriendo
            db.commit()
        try:
            resumen = sincronizar(db, fuente, ciudad, operacion, max_paginas)
            if job:
                job.estado = ScrapingJobEstado.ok
                job.resultado = json.dumps(resumen, ensure_ascii=False)
                job.finalizado_at = datetime.utcnow()
                db.commit()
            return resumen
        except Exception as e:
            if job:
                job.estado = ScrapingJobEstado.error
                job.error = str(e)[:2000]
                job.finalizado_at = datetime.utcnow()
                db.commit()
            return {"ok": False, "error": str(e)}
    finally:
        db.close()
