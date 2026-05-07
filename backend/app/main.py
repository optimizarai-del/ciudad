import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from app.database import Base, engine
from app.routers import auth, users, propiedades, clientes, contratos, calculadora, dashboard, agente, alertas, indices, tokko, pagos, agente_router
from app.routers import cobranza, ventas_router, comprobantes

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CIUDAD — Negocios Inmobiliarios",
    description="#VIVIRMEJOR — plataforma de gestión inmobiliaria",
    version="0.1.0",
)

origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in [auth, users, propiedades, clientes, contratos, calculadora, dashboard, agente, alertas, indices, tokko, pagos]:
    app.include_router(r.router)

app.include_router(agente_router.router)
app.include_router(cobranza.router)
app.include_router(ventas_router.router)
app.include_router(comprobantes.router)


@app.get("/health")
def health():
    return {"status": "ok", "brand": "CIUDAD — Negocios Inmobiliarios", "slogan": "#VIVIRMEJOR"}


@app.on_event("startup")
def _seed_if_empty():
    from app.database import SessionLocal
    from app import models
    db = SessionLocal()
    try:
        if db.query(models.User).count() == 0:
            from app.seed import run as seed_run
            seed_run()
    finally:
        db.close()


@app.on_event("startup")
def _migrar_estados_contrato():
    """
    Migración liviana: 'cerrado' fue removido del enum y reemplazado por 'reservado'.
    Los contratos históricos en 'cerrado' los pasamos a 'vencido' para no inventar
    reservas que nunca existieron.
    """
    from sqlalchemy import text
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        db.execute(text("UPDATE contratos SET estado='vencido' WHERE estado='cerrado'"))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@app.on_event("startup")
def _unificar_tasas_municipales():
    """
    Migración: ahora tasa_municipal = tasa_municipal + impuesto_inmobiliario.
    Lo hacemos una sola vez (marca: ciudad_settings.tasas_unificadas).
    """
    from sqlalchemy import text
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS ciudad_settings (
                key VARCHAR PRIMARY KEY,
                value VARCHAR
            )
        """))
        ya = db.execute(text("SELECT value FROM ciudad_settings WHERE key='tasas_unificadas'")).first()
        if not ya:
            db.execute(text("""
                UPDATE propiedades
                SET tasa_municipal = COALESCE(tasa_municipal, 0) + COALESCE(impuesto_inmobiliario, 0),
                    impuesto_inmobiliario = 0
            """))
            db.execute(text("INSERT INTO ciudad_settings (key, value) VALUES ('tasas_unificadas', '1')"))
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
