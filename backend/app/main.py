import logging
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

# override=True: si hay una variable previa en el shell (vacía o con otro valor),
# el .env del proyecto manda. Importante en entornos donde el shell hereda
# variables de sesiones anteriores.
load_dotenv(override=True)

from app.database import Base, engine
# Importar models_ventas para que sus tablas ventas_* se registren en el
# metadata antes del create_all (módulo Ventas aislado — ver plan sección 15).
from app import models_ventas  # noqa: F401
from app.routers import auth, users, propiedades, clientes, contratos, calculadora, dashboard, agente, alertas, indices, tokko, pagos, agente_router
from app.routers import cobranza, ventas_router, ventas_crm, ventas_fase23, comprobantes
from app.routers import liquidaciones, finanzas, adjuntos, recordatorios, storage_migracion, demo_fixture, tasas_msr, tasas_mensuales, refacciones, versiones
from app.routers import historial as historial_router
from app.security import get_current_user

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CIUDAD — Negocios Inmobiliarios",
    description="#VIVIRMEJOR — plataforma de gestión inmobiliaria",
    version="0.1.0",
)

# CORS: permitir el dominio productivo de Easypanel + cualquier subdominio
# de optimizar-ia.com (api.*, www.*, ciudad.*, etc.) + dev local.
# Usamos allow_origin_regex como fallback robusto: si la env var
# CORS_ORIGINS se pierde o queda vacía en un rebuild, el regex sigue
# permitiendo el tráfico desde el dominio real. Eso evita que la app
# quede caída por una configuración mal puesta.
_env_origins = os.getenv("CORS_ORIGINS", "").strip()
if _env_origins:
    origins = [o.strip() for o in _env_origins.split(",") if o.strip()]
else:
    origins = []

# Hardcoded baseline: estos siempre se aceptan, en cualquier deploy.
_BASELINE_ORIGINS = [
    "https://ciudad.optimizar-ia.com",
    "https://www.ciudad.optimizar-ia.com",
    "http://localhost:5173",
    "http://localhost:4173",
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
]
for o in _BASELINE_ORIGINS:
    if o not in origins:
        origins.append(o)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    # Acepta también CUALQUIER subdominio https://*.optimizar-ia.com
    # Esto es safety-net por si en el futuro se mueve a otro subdominio.
    allow_origin_regex=r"https?://(.*\.)?optimizar-ia\.com$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
print(f"[CORS] origins permitidos: {origins}")

for r in [auth, users, propiedades, clientes, contratos, calculadora, dashboard, agente, alertas, indices, tokko, pagos]:
    app.include_router(r.router)

app.include_router(agente_router.router)
app.include_router(cobranza.router)
app.include_router(ventas_router.router)
app.include_router(ventas_crm.router)
app.include_router(ventas_fase23.router)
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
app.include_router(versiones.router)
app.include_router(historial_router.router)


@app.get("/health")
def health():
    # Exponemos el GIT_SHA del build (Easypanel lo pasa como build-arg)
    # para poder diagnosticar si el deploy está sincronizado con el repo.
    return {
        "status": "ok",
        "brand":  "CIUDAD — Negocios Inmobiliarios",
        "slogan": "#VIVIRMEJOR",
        "git_sha": os.getenv("GIT_SHA", "unknown")[:12],
        "build_marker": "post-savepoints-fix",  # cambia con cada deploy importante
    }


@app.get("/api/debug/contratos-vigentes")
def debug_contratos_vigentes(user=Depends(get_current_user)):
    """Endpoint de diagnóstico — requiere usuario autenticado con rol admin —
    para verificar qué contratos vigentes y pagos hay en la DB del deploy
    actual. No expone PII ni datos sensibles. Solo conteos y códigos.
    Quitar cuando el bug esté resuelto."""
    from app import models
    if user.role != models.UserRole.admin:
        raise HTTPException(403, "Solo admin")
    from app.database import SessionLocal
    from sqlalchemy import text, inspect
    from app.database import IS_POSTGRES, CIUDAD_SCHEMA
    db = SessionLocal()
    try:
        ins = inspect(db.bind)
        schema = CIUDAD_SCHEMA if IS_POSTGRES else None
        out = {"schema": schema, "tablas": ins.get_table_names(schema=schema)}
        qual_c = f'"{CIUDAD_SCHEMA}".contratos' if IS_POSTGRES else "contratos"
        qual_p = f'"{CIUDAD_SCHEMA}".pagos' if IS_POSTGRES else "pagos"
        # Conteos por workspace
        out["contratos_vigentes_reales"] = db.execute(text(
            f"SELECT COUNT(*) FROM {qual_c} WHERE estado='vigente' AND is_demo=false"
        )).scalar()
        out["contratos_vigentes_demo"]   = db.execute(text(
            f"SELECT COUNT(*) FROM {qual_c} WHERE estado='vigente' AND is_demo=true"
        )).scalar()
        out["pagos_reales_pendientes"]   = db.execute(text(
            f"SELECT COUNT(*) FROM {qual_p} WHERE is_demo=false AND estado='pendiente'"
        )).scalar()
        out["pagos_demo_pendientes"]     = db.execute(text(
            f"SELECT COUNT(*) FROM {qual_p} WHERE is_demo=true AND estado='pendiente'"
        )).scalar()
        # Últimos contratos vigentes reales
        rows = db.execute(text(f"""
            SELECT c.codigo, c.fecha_inicio, c.fecha_fin,
                   (SELECT COUNT(*) FROM {qual_p} WHERE contrato_id=c.id) as np
            FROM {qual_c} c
            WHERE c.estado='vigente' AND c.is_demo=false
            ORDER BY c.id DESC LIMIT 10
        """)).fetchall()
        out["ultimos_contratos_reales"] = [
            {"codigo": r[0], "fechas": f"{r[1]}->{r[2]}", "pagos": r[3]}
            for r in rows
        ]
        return out
    finally:
        db.close()


# ─── Servir el frontend buildeado (modo local autocontenido) ──────────────────
# Cuando la app corre como "versión local" (bajada desde Herramientas →
# Versiones local), el ZIP incluye el frontend ya buildeado en `app/static/`.
# Si esa carpeta existe Y la env var SERVE_FRONTEND=true, la montamos en "/"
# para que un único servidor en localhost:8000 sirva API + UI.
#
# IMPORTANTE: en producción cloud (Easypanel) DEJAR `SERVE_FRONTEND` SIN definir.
# El catch-all del SPA puede interceptar requests como `/api/propiedades`
# (sin barra final) y devolver 404 en lugar de que FastAPI haga su redirect 307
# a `/api/propiedades/` (que es lo registrado por @router.get("/")).
# Por eso lo dejamos opt-in via env var, solo para el ZIP local que no tiene
# subdominio API separado.
from pathlib import Path as _Path
from fastapi.staticfiles import StaticFiles as _StaticFiles
from fastapi.responses import FileResponse as _FileResponse
from fastapi import Request as _Request, HTTPException as _HTTPException

_FRONT_DIR = _Path(__file__).parent / "static"
_SERVE_FRONTEND = os.getenv("SERVE_FRONTEND", "").lower() in ("1", "true", "yes", "on")

if _SERVE_FRONTEND and _FRONT_DIR.exists() and (_FRONT_DIR / "index.html").exists():
    app.mount("/assets", _StaticFiles(directory=str(_FRONT_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def _spa_fallback(full_path: str, request: _Request):
        # Si alguien pidió algo del API que no existe, devolver 404 normal
        if full_path.startswith("api") or full_path == "health":
            raise _HTTPException(404, "Not found")
        # Archivos estáticos sueltos (favicon, robots.txt, etc.)
        candidato = _FRONT_DIR / full_path
        if candidato.is_file():
            return _FileResponse(candidato)
        # Default: servir el index.html (lo maneja React Router)
        return _FileResponse(_FRONT_DIR / "index.html")


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
        logger.exception("[migrar] _migrar_tokko_a_venta falló; se hace rollback y se continúa el arranque")
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
        logger.exception("[migrar] _migrar_schema falló; se hace rollback y se continúa el arranque")
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
            cols_k = {c["name"] for c in ins.get_columns("contratos", schema=schema)}

        # contratos: campos para importación IA (mora, días de pago, policies, inventario)
        nuevas_cols_contrato = [
            ("mora_diaria_porc", "FLOAT DEFAULT 0"),
            ("dia_inicio_pago", "INTEGER DEFAULT 1"),
            ("dia_vencimiento_pago", "INTEGER DEFAULT 10"),
            ("policies", "TEXT"),
            ("inventario", "TEXT"),
        ]
        for col, ddl in nuevas_cols_contrato:
            if col not in cols_k:
                try:
                    db.execute(text(f"ALTER TABLE {qual}contratos ADD COLUMN {col} {ddl}"))
                    db.commit()
                except Exception:
                    logger.exception("[migrar] contratos.%s: falló el ALTER TABLE; rollback y se continúa", col)
                    db.rollback()

        # contrato_inquilinos: tabla pivote para múltiples inquilinos por contrato.
        # Idempotente: si ya existe no toca. Si no, la crea con checkfirst=True
        # para no romper si otro worker la creó al mismo tiempo.
        try:
            ins_fresh = inspect(engine)  # refresh inspector por si cambió en este loop
            if "contrato_inquilinos" not in ins_fresh.get_table_names(schema=schema):
                from app.models import ContratoInquilino
                ContratoInquilino.__table__.create(engine, checkfirst=True)
                print("[migrar] creada tabla contrato_inquilinos")
        except Exception:
            logger.exception("[migrar] crear contrato_inquilinos falló; se continúa")
            try: db.rollback()
            except Exception: pass

        # garantes: tabla propia para fiadores/garantes de cada contrato.
        # Se guardan inline (no son Clientes) para que NO aparezcan en los
        # listados de Clientes/Propietarios. Idempotente.
        try:
            ins_fresh = inspect(engine)
            if "garantes" not in ins_fresh.get_table_names(schema=schema):
                from app.models import Garante
                Garante.__table__.create(engine, checkfirst=True)
                print("[migrar] creada tabla garantes")
        except Exception:
            logger.exception("[migrar] crear garantes falló; se continúa")
            try: db.rollback()
            except Exception: pass

        # pagos: monto_pagado_transferencia (parte abonada por transferencia)
        cols_pagos = {c["name"] for c in ins.get_columns("pagos", schema=schema)}
        if "monto_pagado_transferencia" not in cols_pagos:
            try:
                db.execute(text(f"ALTER TABLE {qual}pagos ADD COLUMN monto_pagado_transferencia FLOAT DEFAULT 0"))
                db.commit()
            except Exception:
                logger.exception("[migrar] pagos.monto_pagado_transferencia: falló el ALTER TABLE; rollback y se continúa")
                db.rollback()

        # clientes: tipo_documento y nacionalidad (para extracción IA)
        cols_cli = {c["name"] for c in ins.get_columns("clientes", schema=schema)}
        nuevas_cols_cliente = [
            ("tipo_documento", "VARCHAR"),
            ("nacionalidad", "VARCHAR"),
        ]
        for col, ddl in nuevas_cols_cliente:
            if col not in cols_cli:
                try:
                    db.execute(text(f"ALTER TABLE {qual}clientes ADD COLUMN {col} {ddl}"))
                    db.commit()
                except Exception:
                    logger.exception("[migrar] clientes.%s: falló el ALTER TABLE; rollback y se continúa", col)
                    db.rollback()

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
                        except Exception:
                            logger.exception("[migrar] enum propiedadtipo += %s falló; se continúa", nuevo_tipo)
            except Exception:
                logger.exception("[migrar] enum propiedadtipo: falló la conexión AUTOCOMMIT; se continúa")

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
    except Exception:
        logger.exception("[migrar] _migrar_storage_path falló; rollback y se continúa el arranque")
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
            except Exception:
                db.rollback()
                logger.exception("[migrar] %s.is_demo falló; rollback y se continúa", tabla)

        # Postgres: agregar valor admin_demo al enum userrole
        if IS_POSTGRES:
            try:
                with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as raw:
                    raw.execute(text(
                        f"ALTER TYPE {qual}userrole ADD VALUE IF NOT EXISTS 'admin_demo'"
                    ))
            except Exception:
                logger.exception("[migrar] enum userrole += admin_demo falló; se continúa")
    except Exception:
        logger.exception("[migrar] _migrar_workspace_demo falló; se continúa el arranque")
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
    except Exception:
        db.rollback()
        logger.exception("[migrar] limpiar codigos vacíos falló; rollback y se continúa")
    finally:
        db.close()


@app.on_event("startup")
def _migrar_contrato_archivado():
    """Agrega columnas archivado + fecha_archivado a contratos. Idempotente."""
    from sqlalchemy import text, inspect
    from app.database import SessionLocal, engine, IS_POSTGRES, CIUDAD_SCHEMA
    schema = CIUDAD_SCHEMA if IS_POSTGRES else None
    qual = f"{CIUDAD_SCHEMA}." if IS_POSTGRES else ""
    db = SessionLocal()
    try:
        cols = {c["name"] for c in inspect(engine).get_columns("contratos", schema=schema)}
        if "archivado" not in cols:
            db.execute(text(
                f"ALTER TABLE {qual}contratos ADD COLUMN archivado BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            db.execute(text(
                f"ALTER TABLE {qual}contratos ADD COLUMN fecha_archivado TIMESTAMP"
            ))
            db.execute(text(
                f"CREATE INDEX IF NOT EXISTS ix_contratos_archivado ON {qual}contratos(archivado)"
            ))
            db.commit()
            print("[migrar] contratos.archivado + fecha_archivado agregadas")
    except Exception:
        db.rollback()
        logger.exception("[migrar] contratos.archivado falló; rollback y se continúa")
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
    except Exception:
        db.rollback()
        logger.exception("[migrar] pagos.detalle_conceptos falló; rollback y se continúa")
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
    except Exception:
        db.rollback()
        logger.exception("[migrar] pagos.liquidacion falló; rollback y se continúa")
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
        except Exception:
            logger.exception("[migrar] enum clienteetapaventa falló; se continúa")

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
    except Exception:
        db.rollback()
        logger.exception("[migrar] clientes.etapa_venta falló; rollback y se continúa")
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
    except Exception:
        db.rollback()
        logger.exception("[migrar] propiedad_propietarios falló; rollback y se continúa")
    finally:
        db.close()


@app.on_event("startup")
def _crear_tabla_versiones_local():
    """Crea la tabla versiones_local si no existe. Idempotente."""
    from sqlalchemy import inspect
    from app.database import engine
    try:
        ins = inspect(engine)
        if "versiones_local" not in ins.get_table_names():
            from app.models import VersionLocal  # noqa
            VersionLocal.__table__.create(engine, checkfirst=True)
            print("[migrar] tabla `versiones_local` creada")
    except Exception:
        logger.exception("[migrar] crear versiones_local falló; se continúa")


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
    except Exception:
        logger.exception("[migrar] crear refacciones falló; se continúa")


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


