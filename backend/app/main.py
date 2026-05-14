import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# override=True: si hay una variable previa en el shell (vacía o con otro valor),
# el .env del proyecto manda. Importante en entornos donde el shell hereda
# variables de sesiones anteriores.
load_dotenv(override=True)

from app.database import Base, engine
from app.routers import auth, users, propiedades, clientes, contratos, calculadora, dashboard, agente, alertas, indices, tokko, pagos, agente_router
from app.routers import cobranza, ventas_router, comprobantes
from app.routers import liquidaciones, finanzas, adjuntos, recordatorios, storage_migracion, demo_fixture, tasas_msr, tasas_mensuales, refacciones

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
app.include_router(liquidaciones.router)
app.include_router(finanzas.router)
app.include_router(adjuntos.router)
app.include_router(recordatorios.router)
app.include_router(storage_migracion.router)
app.include_router(demo_fixture.router)
app.include_router(tasas_msr.router)
app.include_router(tasas_mensuales.router)
app.include_router(refacciones.router)


@app.get("/health")
def health():
    return {"status": "ok", "brand": "CIUDAD — Negocios Inmobiliarios", "slogan": "#VIVIRMEJOR"}


# Las migraciones de schema deben correr ANTES de que cualquier query toque
# las tablas (el seed inicial las consulta, así que debe ir al final).

@app.on_event("startup")
def _migrar_tokko_a_venta():
    """
    Las propiedades importadas desde Tokko se cargaron antes con
    modalidad=alquiler y el precio en precio_alquiler. Tokko es solo venta —
    movemos el precio y forzamos la modalidad. Idempotente con marker en
    ciudad_settings.

    Sólo corre en SQLite (DB legacy). En Postgres arrancamos con DB vacía y
    los enums tienen casts estrictos que rompen estos UPDATE literales.
    """
    from sqlalchemy import text
    from app.database import SessionLocal, IS_POSTGRES
    if IS_POSTGRES:
        return
    db = SessionLocal()
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS ciudad_settings (
                key VARCHAR PRIMARY KEY,
                value VARCHAR
            )
        """))
        ya = db.execute(text("SELECT value FROM ciudad_settings WHERE key='tokko_es_venta'")).first()
        if not ya:
            db.execute(text("""
                UPDATE propiedades
                SET modalidad='venta',
                    precio_venta = COALESCE(precio_venta, 0) + COALESCE(precio_alquiler, 0),
                    precio_alquiler = 0
                WHERE tokko_id IS NOT NULL AND tokko_id != ''
            """))
            db.execute(text("INSERT INTO ciudad_settings (key, value) VALUES ('tokko_es_venta', '1')"))
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@app.on_event("startup")
def _migrar_schema():
    """Migraciones livianas de columnas/datos. Idempotentes.

    Solo corre en SQLite. En Postgres `create_all` deja el schema correcto
    de entrada y los UPDATE legacy con enums fallan por casts estrictos.
    """
    from sqlalchemy import text, inspect
    from app.database import SessionLocal, engine, IS_POSTGRES
    if IS_POSTGRES:
        return
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
def _migrar_storage_path():
    """Agrega la columna `storage_path` a `propiedad_adjuntos` y `comprobantes`
    si no existe todavía. Tanto en SQLite como en Postgres (idempotente).
    También permite que el campo blob legacy sea NULL en propiedad_adjuntos.
    """
    from sqlalchemy import text, inspect
    from app.database import SessionLocal, engine, IS_POSTGRES, CIUDAD_SCHEMA
    schema = CIUDAD_SCHEMA if IS_POSTGRES else None
    qual = f"{CIUDAD_SCHEMA}." if IS_POSTGRES else ""
    db = SessionLocal()
    try:
        ins = inspect(engine)
        # propiedad_adjuntos.storage_path
        cols_adj = {c["name"] for c in ins.get_columns("propiedad_adjuntos", schema=schema)}
        if "storage_path" not in cols_adj:
            db.execute(text(f"ALTER TABLE {qual}propiedad_adjuntos ADD COLUMN storage_path VARCHAR"))
            db.execute(text(f"CREATE INDEX IF NOT EXISTS ix_propiedad_adjuntos_storage_path ON {qual}propiedad_adjuntos(storage_path)"))
            db.commit()
        # comprobantes.storage_path
        cols_c = {c["name"] for c in ins.get_columns("comprobantes", schema=schema)}
        if "storage_path" not in cols_c:
            db.execute(text(f"ALTER TABLE {qual}comprobantes ADD COLUMN storage_path VARCHAR"))
            db.execute(text(f"CREATE INDEX IF NOT EXISTS ix_comprobantes_storage_path ON {qual}comprobantes(storage_path)"))
            db.commit()

        # propiedades: 3 columnas para integración con consulta de deuda
        # de la Municipalidad de Santa Rosa.
        cols_p = {c["name"] for c in ins.get_columns("propiedades", schema=schema)}
        if "numero_referencia" not in cols_p:
            db.execute(text(f"ALTER TABLE {qual}propiedades ADD COLUMN numero_referencia VARCHAR"))
            db.execute(text(f"ALTER TABLE {qual}propiedades ADD COLUMN tasa_consultada_at TIMESTAMP"))
            db.execute(text(f"ALTER TABLE {qual}propiedades ADD COLUMN tasa_detalle TEXT"))
            db.execute(text(f"CREATE INDEX IF NOT EXISTS ix_propiedades_numero_referencia ON {qual}propiedades(numero_referencia)"))
            db.commit()

        # contratos: 4 columnas para archivo firmado/actualizado manualmente
        cols_k = {c["name"] for c in ins.get_columns("contratos", schema=schema)}
        if "archivo_path" not in cols_k:
            db.execute(text(f"ALTER TABLE {qual}contratos ADD COLUMN archivo_path VARCHAR"))
            db.execute(text(f"ALTER TABLE {qual}contratos ADD COLUMN archivo_nombre VARCHAR"))
            db.execute(text(f"ALTER TABLE {qual}contratos ADD COLUMN archivo_mime VARCHAR"))
            db.execute(text(f"ALTER TABLE {qual}contratos ADD COLUMN archivo_subido_at TIMESTAMP"))
            db.execute(text(f"CREATE INDEX IF NOT EXISTS ix_contratos_archivo_path ON {qual}contratos(archivo_path)"))
            db.commit()

        # Agregar valores al enum propiedadtipo si Postgres no los tiene.
        # ALTER TYPE ADD VALUE no puede correr dentro de una transacción;
        # usamos una conexión con AUTOCOMMIT explícito.
        if IS_POSTGRES:
            try:
                with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as raw:
                    for nuevo_tipo in ("oficina", "galpon"):
                        try:
                            raw.execute(text(
                                f"ALTER TYPE {qual}propiedadtipo ADD VALUE IF NOT EXISTS '{nuevo_tipo}'"
                            ))
                        except Exception as e:
                            print(f"[migrar] enum propiedadtipo += {nuevo_tipo}: {e}")
            except Exception as e:
                print(f"[migrar] enum propiedadtipo conn: {e}")

        # blob_b64 antes era NOT NULL. Con Storage habilitado, los uploads
        # nuevos guardan en Storage y dejan blob_b64 = NULL. Hacer la columna
        # nullable si todavía está con la constraint vieja.
        if IS_POSTGRES:
            blob_col = next(
                (c for c in ins.get_columns("propiedad_adjuntos", schema=schema)
                 if c["name"] == "blob_b64"),
                None,
            )
            if blob_col and not blob_col.get("nullable", True):
                db.execute(text(
                    f"ALTER TABLE {qual}propiedad_adjuntos ALTER COLUMN blob_b64 DROP NOT NULL"
                ))
                db.commit()
    except Exception as e:
        print(f"[_migrar_storage_path] {e}")
        db.rollback()
    finally:
        db.close()


@app.on_event("startup")
def _crear_tabla_refacciones():
    """Defensivo: si por algún motivo `create_all` no dejó la tabla creada,
    la creamos manualmente. Idempotente."""
    from sqlalchemy import inspect
    from app.database import engine
    try:
        ins = inspect(engine)
        if "refacciones" not in ins.get_table_names():
            from app.models import Refaccion  # noqa
            Refaccion.__table__.create(engine, checkfirst=True)
            print("[migrar] tabla `refacciones` creada")
    except Exception as e:
        print(f"[migrar] crear refacciones: {e}")


@app.on_event("startup")
def _ensure_storage_buckets():
    """Crea los buckets de Supabase Storage si no existen. Sólo si las env
    vars `SUPABASE_URL` y `SUPABASE_SERVICE_KEY` están configuradas."""
    from app.services import supabase_storage
    if not supabase_storage.enabled():
        return
    ok, msg = supabase_storage.ensure_buckets()
    print(f"[storage] ensure_buckets: ok={ok} | {msg}")


@app.on_event("startup")
async def _start_recordatorios():
    """
    Loop background de recordatorios. Se activa con RECORDATORIOS_ENABLED=true
    en .env (default false para no spamear en dev). Intervalo configurable.
    """
    import os, asyncio
    if os.getenv("RECORDATORIOS_ENABLED", "false").lower() not in ("1", "true", "yes"):
        return
    intervalo = int(os.getenv("RECORDATORIOS_INTERVALO_SEG", "3600"))
    from app.services.recordatorios import loop_recordatorios
    asyncio.create_task(loop_recordatorios(intervalo))


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


