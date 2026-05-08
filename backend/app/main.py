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


# Las migraciones de schema deben correr ANTES de que cualquier query toque
# las tablas (el seed inicial las consulta, así que debe ir al final).

@app.on_event("startup")
def _migrar_schema():
    """Migraciones livianas de columnas/datos. Idempotentes."""
    from sqlalchemy import text, inspect
    from app.database import SessionLocal, engine
    db = SessionLocal()
    try:
        # 1. User.telegram_chat_id (Fase 3 — agente admin con permisos por rol).
        cols = {c["name"] for c in inspect(engine).get_columns("users")}
        if "telegram_chat_id" not in cols:
            db.execute(text("ALTER TABLE users ADD COLUMN telegram_chat_id VARCHAR"))
            db.commit()

        # 2. ContratoEstado: 'cerrado' → 'vencido' (el enum dejó de soportar
        # 'cerrado'; los registros viejos se migran para no inventar reservas).
        db.execute(text("UPDATE contratos SET estado='vencido' WHERE estado='cerrado'"))
        db.commit()

        # 3. Tasas municipales unificadas (impuesto_inmobiliario + tasa_municipal).
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


