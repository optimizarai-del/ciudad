"""
Conexión a la DB. Soporta SQLite (dev local) y Postgres/Supabase (producción).

En Postgres, todas las tablas viven en el schema `ciudad` (aislado del resto
del proyecto Supabase que también aloja n8n_chat_histories en public). El
schema se setea en el search_path al abrir cada conexión.
"""
from sqlalchemy import create_engine, event, MetaData
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ciudad.db")
IS_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))

# SQLAlchemy en versiones recientes usa el dialecto `postgresql://`; algunos
# proveedores devuelven el legacy `postgres://`. Normalizamos.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Schema dedicado para CIUDAD en Postgres. Configurable por si en el futuro
# se migra a una DB propia.
CIUDAD_SCHEMA = os.getenv("CIUDAD_DB_SCHEMA", "ciudad")

if IS_POSTGRES:
    # pool_pre_ping evita errores de "connection has been closed" cuando el
    # pooler de Supabase cierra conexiones idle.
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

    # Forzar search_path a `ciudad` en cada conexión. Así todos los modelos
    # quedan en ese schema sin tocar __table_args__ en cada modelo.
    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute(f"SET search_path TO {CIUDAD_SCHEMA}, public")
        cursor.close()

    metadata = MetaData(schema=CIUDAD_SCHEMA)
else:
    # SQLite local — sin schema, sin search_path.
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    metadata = MetaData()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base(metadata=metadata)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
