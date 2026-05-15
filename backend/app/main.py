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
def _migrar_workspace_demo():
    """Agrega la columna `is_demo` a las tablas principales (idempotente).
    También agrega el valor `admin_demo` al enum userrole en Postgres.

    Esto aísla la data demo del workspace real: usuarios con role=admin_demo
    sólo ven filas con is_demo=True; el resto sólo ve is_demo=False.
    """
    from sqlalchemy import text, inspect
    from app.database import SessionLocal, engine, IS_POSTGRES, CIUDAD_SCHEMA
    schema = CIUDAD_SCHEMA if IS_POSTGRES else None
    qual = f"{CIUDAD_SCHEMA}." if IS_POSTGRES else ""

    tablas_con_is_demo = [
        "propiedades", "clientes", "contratos", "pagos", "leads",
        # refacciones nunca se creó sin is_demo (modelo nuevo), pero
        # corremos por las dudas para que sea idempotente.
        "refacciones",
    ]

    db = SessionLocal()
    try:
        ins = inspect(engine)
        for tabla in tablas_con_is_demo:
            try:
                if tabla not in ins.get_table_names(schema=schema):
                    continue
                cols = {c["name"] for c in ins.get_columns(tabla, schema=schema)}
                if "is_demo" not in cols:
                    # Default FALSE + NOT NULL; las filas existentes quedan en False
                    # (que es lo que queremos: la data actual es "real", no demo).
                    db.execute(text(
                        f"ALTER TABLE {qual}{tabla} ADD COLUMN is_demo BOOLEAN NOT NULL DEFAULT FALSE"
                    ))
                    db.execute(text(
                        f"CREATE INDEX IF NOT EXISTS ix_{tabla}_is_demo ON {qual}{tabla}(is_demo)"
                    ))
                    db.commit()
                    print(f"[migrar] {tabla}.is_demo agregada")
            except Exception as e:
                db.rollback()
                print(f"[migrar] {tabla}.is_demo falló: {e}")

        # Postgres: agregar valor admin_demo al enum userrole
        if IS_POSTGRES:
            try:
                with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as raw:
                    raw.execute(text(
                        f"ALTER TYPE {qual}userrole ADD VALUE IF NOT EXISTS 'admin_demo'"
                    ))
            except Exception as e:
                print(f"[migrar] enum userrole += admin_demo: {e}")
    except Exception as e:
        print(f"[_migrar_workspace_demo] {e}")
    finally:
        db.close()


@app.on_event("startup")
def _limpiar_codigos_contrato_vacios():
    """Convierte contratos.codigo='' (cadena vacía) en NULL.

    El UNIQUE INDEX en `codigo` permite múltiples NULL pero NO permite
    múltiples cadenas vacías, así que si quedó algún registro huérfano
    con codigo='' bloquea cualquier inserción que no traiga código.
    Idempotente: si no hay filas afectadas, no hace nada.
    """
    from sqlalchemy import text
    from app.database import SessionLocal, IS_POSTGRES, CIUDAD_SCHEMA
    qual = f"{CIUDAD_SCHEMA}." if IS_POSTGRES else ""
    db = SessionLocal()
    try:
        # 1) Vaciar codigos vacíos.
        res = db.execute(text(
            f"UPDATE {qual}contratos SET codigo = NULL "
            f"WHERE codigo IS NOT NULL AND TRIM(codigo) = ''"
        ))
        if res.rowcount:
            print(f"[migrar] contratos.codigo='' → NULL en {res.rowcount} fila(s)")
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[migrar] limpiar codigos vacíos: {e}")
    finally:
        db.close()


@app.on_event("startup")
def _migrar_detalle_conceptos():
    """Agrega columna `detalle_conceptos` (TEXT/JSON) a `pagos`. Idempotente."""
    from sqlalchemy import text, inspect
    from app.database import SessionLocal, engine, IS_POSTGRES, CIUDAD_SCHEMA
    schema = CIUDAD_SCHEMA if IS_POSTGRES else None
    qual = f"{CIUDAD_SCHEMA}." if IS_POSTGRES else ""
    db = SessionLocal()
    try:
        cols = {c["name"] for c in inspect(engine).get_columns("pagos", schema=schema)}
        if "detalle_conceptos" not in cols:
            db.execute(text(f"ALTER TABLE {qual}pagos ADD COLUMN detalle_conceptos TEXT"))
            db.commit()
            print("[migrar] pagos.detalle_conceptos agregada")
    except Exception as e:
        db.rollback()
        print(f"[migrar] detalle_conceptos: {e}")
    finally:
        db.close()


@app.on_event("startup")
def _migrar_liquidacion_propietario():
    """Agrega columnas de liquidación al propietario sobre `pagos`. Idempotente."""
    from sqlalchemy import text, inspect
    from app.database import SessionLocal, engine, IS_POSTGRES, CIUDAD_SCHEMA
    schema = CIUDAD_SCHEMA if IS_POSTGRES else None
    qual = f"{CIUDAD_SCHEMA}." if IS_POSTGRES else ""
    db = SessionLocal()
    try:
        ins = inspect(engine)
        cols = {c["name"] for c in ins.get_columns("pagos", schema=schema)}
        nuevas = [
            ("liquidado_propietario", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("fecha_liquidacion_propietario", "DATE"),
            ("monto_liquidado_propietario", "FLOAT"),
            ("notas_liquidacion", "TEXT"),
        ]
        for nombre, tipo in nuevas:
            if nombre not in cols:
                db.execute(text(f"ALTER TABLE {qual}pagos ADD COLUMN {nombre} {tipo}"))
                db.commit()
                print(f"[migrar] pagos.{nombre} agregada")
        if "liquidado_propietario" not in cols:
            db.execute(text(
                f"CREATE INDEX IF NOT EXISTS ix_pagos_liquidado_propietario ON {qual}pagos(liquidado_propietario)"
            ))
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"[migrar] pagos.liquidacion: {e}")
    finally:
        db.close()


@app.on_event("startup")
def _migrar_etapa_venta():
    """Agrega la columna `etapa_venta` y el enum clienteetapaventa (Postgres).

    Idempotente. El enum se crea si no existe; la columna nullable se agrega
    sin default — los registros previos quedan en NULL, que para inquilinos
    y propietarios es correcto (no aplica pipeline).
    """
    from sqlalchemy import text, inspect
    from app.database import SessionLocal, engine, IS_POSTGRES, CIUDAD_SCHEMA
    schema = CIUDAD_SCHEMA if IS_POSTGRES else None
    qual = f"{CIUDAD_SCHEMA}." if IS_POSTGRES else ""

    # 1. Crear el enum (Postgres). En SQLite se crea automáticamente con la columna.
    if IS_POSTGRES:
        try:
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as raw:
                # Existe?
                existe = raw.execute(text(
                    f"SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
                    f"WHERE t.typname='clienteetapaventa' AND n.nspname='{CIUDAD_SCHEMA}'"
                )).first()
                if not existe:
                    raw.execute(text(
                        f"CREATE TYPE {qual}clienteetapaventa AS ENUM "
                        f"('prospecto','seguimiento','sena','comprador','no_interesado')"
                    ))
                    print("[migrar] enum clienteetapaventa creado")
        except Exception as e:
            print(f"[migrar] enum clienteetapaventa: {e}")

    # 2. ALTER TABLE clientes ADD COLUMN etapa_venta
    db = SessionLocal()
    try:
        ins = inspect(engine)
        cols = {c["name"] for c in ins.get_columns("clientes", schema=schema)}
        if "etapa_venta" not in cols:
            tipo_col = f"{qual}clienteetapaventa" if IS_POSTGRES else "VARCHAR"
            db.execute(text(
                f"ALTER TABLE {qual}clientes ADD COLUMN etapa_venta {tipo_col}"
            ))
            db.execute(text(
                f"CREATE INDEX IF NOT EXISTS ix_clientes_etapa_venta ON {qual}clientes(etapa_venta)"
            ))
            db.commit()
            print("[migrar] clientes.etapa_venta agregada")
    except Exception as e:
        db.rollback()
        print(f"[migrar] clientes.etapa_venta: {e}")
    finally:
        db.close()


@app.on_event("startup")
def _crear_tabla_propiedad_propietarios():
    """Crea la tabla pivote propiedad↔propietario y migra los registros
    existentes (Propiedad.propietario_id) a una fila pivote es_principal=true.
    Idempotente.
    """
    from sqlalchemy import text, inspect
    from app.database import SessionLocal, engine, IS_POSTGRES, CIUDAD_SCHEMA
    schema = CIUDAD_SCHEMA if IS_POSTGRES else None
    qual = f"{CIUDAD_SCHEMA}." if IS_POSTGRES else ""

    db = SessionLocal()
    try:
        ins = inspect(engine)
        if "propiedad_propietarios" not in ins.get_table_names(schema=schema):
            from app.models import PropiedadPropietario  # noqa
            PropiedadPropietario.__table__.create(engine, checkfirst=True)
            print("[migrar] tabla propiedad_propietarios creada")

        # Backfill: para cada propiedad con propietario_id que no tenga aún
        # ninguna fila pivote, crear una con es_principal=True.
        # Postgres + SQLite ambos soportan esta forma.
        db.execute(text(f"""
            INSERT INTO {qual}propiedad_propietarios (propiedad_id, cliente_id, es_principal, created_at)
            SELECT p.id, p.propietario_id, TRUE, CURRENT_TIMESTAMP
            FROM {qual}propiedades p
            WHERE p.propietario_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM {qual}propiedad_propietarios pp
                  WHERE pp.propiedad_id = p.id
              )
        """))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[migrar] propiedad_propietarios: {e}")
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


