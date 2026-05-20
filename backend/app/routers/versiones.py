"""
Versiones local — snapshots descargables para uso offline.

Genera un ZIP con:
  · Código fuente del backend (Python, sin venv ni .env)
  · Código fuente del frontend (React/Vite, sin node_modules ni dist)
  · Dump completo de la base de datos en SQLite (archivo ciudad.db)
  · .env pre-configurado para modo local (SQLite, sin Supabase)
  · Scripts de arranque con un doble clic (INICIAR.bat / iniciar.sh)
  · README con instrucciones paso a paso

El ZIP es streameable: se genera en memoria y se descarga directamente.
Cada descarga queda registrada en la tabla `versiones_local`.
"""
import io
import json
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.database import get_db, engine, IS_POSTGRES, CIUDAD_SCHEMA
from app.security import get_current_user
from app import models

router = APIRouter(prefix="/api/versiones", tags=["versiones"])

# ─── Rutas del proyecto ───────────────────────────────────────────────────────
# __file__ = .../backend/app/routers/versiones.py
_BACKEND_ROOT  = Path(__file__).parents[2]      # .../backend
_PROJECT_ROOT  = _BACKEND_ROOT.parent           # raíz del monorepo
_FRONTEND_ROOT = _PROJECT_ROOT / "frontend"

# Dirs/archivos a excluir al empaquetar
_SKIP_BACKEND  = {
    "__pycache__", ".venv", "venv", "env", ".env",
    ".git", ".mypy_cache", ".pytest_cache",
    "ciudad.db", "*.db", "*.db-shm", "*.db-wal",
    "*.pyc", "*.pyo", "*.egg-info", "dist", "build",
}
_SKIP_FRONTEND = {
    "node_modules", "dist", ".git",
    ".cache", ".turbo", ".next",
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _skip(rel: Path, excluir: set) -> bool:
    """Devuelve True si alguna parte del path relativo debe excluirse."""
    for parte in rel.parts:
        if parte in excluir or parte.startswith("."):
            return True
    return False


def _add_dir(zf: zipfile.ZipFile, src: Path, arc_prefix: str, excluir: set):
    """Agrega recursivamente src/ al zip bajo arc_prefix/."""
    for item in src.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(src)
        if _skip(rel, excluir):
            continue
        try:
            zf.write(item, f"{arc_prefix}/{rel.as_posix()}")
        except Exception:
            pass  # skip archivos no legibles (ej. sockets)


def _export_sqlite(sqlite_path: str) -> dict:
    """Exporta todas las tablas de la DB activa a un archivo SQLite nuevo.

    Devuelve {tabla: cantidad_de_filas}.
    Convierte todos los valores a TEXT para máxima compatibilidad con SQLite.
    """
    schema = CIUDAD_SCHEMA if IS_POSTGRES else None
    qual   = f"{CIUDAD_SCHEMA}." if IS_POSTGRES else ""
    skip   = {"alembic_version", "ciudad_settings"}

    inspector = sa_inspect(engine)
    tables    = inspector.get_table_names(schema=schema)

    totales: dict = {}
    lite = sqlite3.connect(sqlite_path)

    try:
        with engine.connect() as conn:
            for table in sorted(tables):
                if table in skip:
                    continue

                cols      = inspector.get_columns(table, schema=schema)
                col_names = [c["name"] for c in cols]

                # Crear tabla SQLite con todos los campos como TEXT
                defs = ", ".join(f'"{n}" TEXT' for n in col_names)
                lite.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({defs})')

                rows = conn.execute(
                    text(f'SELECT * FROM {qual}"{table}"')
                ).fetchall()

                if rows:
                    ph = ", ".join("?" for _ in col_names)
                    lite.executemany(
                        f'INSERT OR IGNORE INTO "{table}" VALUES ({ph})',
                        [
                            tuple(str(v) if v is not None else None for v in row)
                            for row in rows
                        ],
                    )

                totales[table] = len(rows)

        lite.commit()
    finally:
        lite.close()

    return totales


def _build_zip(version_name: str, sqlite_path: str, tablas: dict) -> bytes:
    """Construye el ZIP completo en memoria y retorna los bytes."""
    p = version_name  # prefijo = carpeta raíz dentro del ZIP
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    # ── Scripts de arranque ────────────────────────────────────────────────

    bat = rf"""@echo off
setlocal
cd /d "%~dp0"
echo.
echo ===================================================
echo   CIUDAD ^| Version local  ({version_name})
echo ===================================================
echo.

:: Verificar Python
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado.
    echo Instala Python 3.10+ desde  https://www.python.org/downloads/
    echo Marcar "Add to PATH" durante la instalacion.
    pause
    exit /b 1
)

:: Entorno virtual + dependencias
echo [1/4] Preparando entorno Python...
cd backend
if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate
pip install -r requirements.txt --quiet
cd ..

:: Frontend (opcional, requiere Node.js)
where node >nul 2>&1
if errorlevel 1 (
    echo [2/4] Node.js no encontrado ^(solo API disponible^).
    echo       Instala desde  https://nodejs.org/  para el frontend visual.
    echo.
    echo [3/4] Iniciando backend en  http://localhost:8000
    start "CIUDAD Backend" cmd /c "cd /d "%~dp0backend" && call venv\Scripts\activate && python run.py"
    timeout /t 4 /nobreak >nul
    start http://localhost:8000
) else (
    echo [2/4] Preparando frontend...
    cd frontend
    if not exist node_modules (
        echo       Instalando dependencias Node ^(primera vez, puede tardar unos minutos^)...
        call npm install --silent
    )
    cd ..
    echo [3/4] Iniciando backend en  http://localhost:8000
    start "CIUDAD Backend" cmd /c "cd /d "%~dp0backend" && call venv\Scripts\activate && python run.py"
    echo [4/4] Iniciando frontend en  http://localhost:5173
    start "CIUDAD Frontend" cmd /c "cd /d "%~dp0frontend" && npm run dev"
    timeout /t 5 /nobreak >nul
    start http://localhost:5173
)

echo.
echo  CIUDAD iniciada correctamente.
echo  Cierra esta ventana para detener todos los servicios.
echo.
pause
"""

    sh = f"""#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo ""
echo "==================================================="
echo "  CIUDAD | Version local  ({version_name})"
echo "==================================================="
echo ""

# ── Backend ────────────────────────────────────────────
echo "[1] Preparando entorno Python..."
cd backend
python3 -m venv venv 2>/dev/null || true
source venv/bin/activate
pip install -r requirements.txt -q
python run.py &
BACKEND_PID=$!
cd ..

# ── Frontend ───────────────────────────────────────────
if command -v node &>/dev/null; then
    echo "[2] Preparando frontend..."
    cd frontend
    [ ! -d node_modules ] && npm install -q
    npm run dev &
    FRONTEND_PID=$!
    cd ..
    sleep 5
    URL="http://localhost:5173"
else
    echo "[2] Node.js no encontrado. Solo disponible la API."
    sleep 2
    URL="http://localhost:8000"
fi

# Abrir navegador (Mac + Linux)
( open "$URL" 2>/dev/null || xdg-open "$URL" 2>/dev/null || true ) &

echo ""
echo " CIUDAD iniciada en  $URL"
echo " Presiona Ctrl+C para detener."
echo ""
wait $BACKEND_PID
"""

    env_backend = """# Configuración local — SQLite, sin Supabase
DATABASE_URL=sqlite:///./ciudad.db
SECRET_KEY=ciudad-local-secret-key-offline

# CORS: permite tanto el puerto de Vite como el de preview
CORS_ORIGINS=http://localhost:5173,http://localhost:4173,http://localhost:8000,http://127.0.0.1:5173

# Email — descomentá para activar envío de comprobantes
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=tu@email.com
# SMTP_PASS=tu-contraseña-de-aplicacion
# EMAIL_FROM=tu@email.com
"""

    env_frontend = """# API local
VITE_API_URL=http://localhost:8000
"""

    # Resumen de tablas para el README
    resumen_tablas = "\n".join(
        f"  · {t:<30} {n:>6} fila{'s' if n != 1 else ''}"
        for t, n in sorted(tablas.items())
        if n > 0
    )

    readme = f"""CIUDAD — Negocios Inmobiliarios
Versión local generada el {now_str}

=== INSTRUCCIONES RÁPIDAS ===

WINDOWS
  Hacer doble clic en:  INICIAR.bat

MAC / LINUX
  Abrir una terminal en esta carpeta y ejecutar:
    chmod +x iniciar.sh
    ./iniciar.sh

=== REQUISITOS ===

  Python 3.10+  →  https://www.python.org/downloads/
                   (marcar "Add Python to PATH" durante la instalación)

  Node.js 18+   →  https://nodejs.org/
                   (para el frontend visual; sin Node sólo corre la API)

=== PRIMERA VEZ ===

  El script instala automáticamente todas las dependencias Python (venv)
  y Node (node_modules) la primera vez que se ejecuta.
  Las siguientes ejecuciones arrancan directamente sin instalar nada.

=== BASE DE DATOS ===

  El archivo  backend/ciudad.db  es una copia SQLite de todos los datos
  exportados desde la plataforma en la nube al momento de esta descarga.
  Es una copia FIJA — los cambios locales no se sincronizan con la nube.
  Para obtener datos actualizados, generá una nueva versión desde
  la plataforma en:  Herramientas → Versiones local.

=== TABLAS EXPORTADAS ===

{resumen_tablas}

=== ACCESO ===

  Frontend completo:  http://localhost:5173
  Solo API:           http://localhost:8000
  Salud del backend:  http://localhost:8000/health

=== SOPORTE ===

  CIUDAD — Negocios Inmobiliarios · #VIVIRMEJOR
"""

    # ── Armar el ZIP ───────────────────────────────────────────────────────
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:

        # Base de datos SQLite
        zf.write(sqlite_path, f"{p}/backend/ciudad.db")

        # Código fuente del backend
        if _BACKEND_ROOT.exists():
            _add_dir(zf, _BACKEND_ROOT, f"{p}/backend", _SKIP_BACKEND)

        # .env local para el backend
        zf.writestr(f"{p}/backend/.env", env_backend)

        # Código fuente del frontend
        if _FRONTEND_ROOT.exists():
            _add_dir(zf, _FRONTEND_ROOT, f"{p}/frontend", _SKIP_FRONTEND)

        # .env local para el frontend
        zf.writestr(f"{p}/frontend/.env.local", env_frontend)

        # Scripts de arranque
        zf.writestr(f"{p}/INICIAR.bat", bat)
        info_sh = zipfile.ZipInfo(f"{p}/iniciar.sh")
        info_sh.external_attr = 0o755 << 16   # chmod +x en sistemas Unix
        zf.writestr(info_sh, sh)

        # README
        zf.writestr(f"{p}/README.txt", readme)

    return buf.getvalue()


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("")
def listar_versiones(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Devuelve las últimas 50 versiones locales generadas (más recientes primero)."""
    rows = (
        db.query(models.VersionLocal)
        .order_by(models.VersionLocal.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id":         v.id,
            "nombre":     v.nombre,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "size_bytes": v.size_bytes,
            "tablas":     json.loads(v.tablas) if v.tablas else {},
            "notas":      v.notas,
        }
        for v in rows
    ]


@router.post("/crear")
def crear_version(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Genera el snapshot ZIP, registra la descarga y la retorna como stream."""

    ts           = datetime.now().strftime("%Y%m%d-%H%M%S")
    version_name = f"ciudad-v{ts}"

    # 1. Exportar DB → SQLite temporal
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        sqlite_path = tmp.name

    try:
        tablas = _export_sqlite(sqlite_path)
    except Exception as e:
        try:
            os.unlink(sqlite_path)
        except OSError:
            pass
        raise HTTPException(500, f"Error exportando la base de datos: {e}")

    # 2. Generar ZIP en memoria
    try:
        zip_bytes = _build_zip(version_name, sqlite_path, tablas)
    except Exception as e:
        raise HTTPException(500, f"Error generando el ZIP: {e}")
    finally:
        try:
            os.unlink(sqlite_path)
        except OSError:
            pass

    size_bytes = len(zip_bytes)

    # 3. Registrar en versiones_local
    ver = models.VersionLocal(
        nombre     = version_name,
        size_bytes = size_bytes,
        tablas     = json.dumps(tablas),
        notas      = None,
    )
    db.add(ver)
    try:
        db.commit()
    except Exception:
        db.rollback()   # no crítico si falla el registro

    # 4. Stream al cliente
    filename = f"{version_name}.zip"
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length":      str(size_bytes),
        },
    )
