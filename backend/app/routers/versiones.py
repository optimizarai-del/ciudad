"""
Versiones local — snapshots descargables y autocontenidos.

Genera un ZIP con TODO lo necesario para correr la plataforma en una PC
sin instalar nada externo:

  · Código del backend (FastAPI)
  · Frontend YA BUILDEADO (no requiere Node ni Vite) — servido por FastAPI
  · Dump completo de la base de datos en SQLite (ciudad.db)
  · Python 3.12 embebido (Windows) + wheels offline de todas las deps
  · Scripts de arranque con doble clic (INICIAR.bat / iniciar.sh)
  · .env pre-configurado para modo local

Estructura del ZIP:

  ciudad-vYYYYMMDD-HHMMSS/
  ├── INICIAR.bat           ← Windows: doble click (autocontenido)
  ├── iniciar.sh            ← Mac/Linux: doble click (requiere Python 3)
  ├── LEEME.txt
  ├── runtime-windows/
  │   ├── python/           ← Python 3.12 embebido (~30 MB)
  │   └── wheels/           ← wheels offline para Windows amd64
  └── backend/
      ├── app/
      │   └── static/       ← frontend buildeado (sirve FastAPI)
      ├── ciudad.db         ← snapshot SQLite
      ├── requirements.txt
      └── .env
"""
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.database import get_db, engine, IS_POSTGRES, CIUDAD_SCHEMA
from app.security import get_current_user
from app.services.workspace import is_demo_user
from app import models

router = APIRouter(prefix="/api/versiones", tags=["versiones"])

# ─── Rutas del proyecto ───────────────────────────────────────────────────────
# __file__ = .../backend/app/routers/versiones.py
_BACKEND_ROOT  = Path(__file__).parents[2]      # .../backend
_PROJECT_ROOT  = _BACKEND_ROOT.parent           # raíz del monorepo
_FRONTEND_ROOT = _PROJECT_ROOT / "frontend"
_FRONTEND_DIST = _FRONTEND_ROOT / "dist"

# Frontend pre-buildeado dentro del backend. Se usa en producción (Docker)
# donde no hay Node — se buildea localmente con `npm run build` y se copia
# a esta ubicación con scripts/copy_frontend.sh (o copy_frontend.bat).
# En dev local, si esta carpeta existe se usa; si no, se buildea on-the-fly.
_FRONTEND_PREBUILT = _BACKEND_ROOT / "app" / "static"

# Cache de runtimes (Python embebido y wheels). Sobrevive entre requests pero
# si se pierde no pasa nada — se rebaja la próxima vez.
_CACHE_ROOT = Path(tempfile.gettempdir()) / "ciudad-bundle-cache"
_CACHE_PY_WIN = _CACHE_ROOT / "python-3.12.7-embed-amd64"
_CACHE_WHEELS_WIN = _CACHE_ROOT / "wheels-win-amd64"

# Versión de Python embebido que se va a empaquetar
_PY_VERSION = "3.12.7"
_PY_EMBED_URL = f"https://www.python.org/ftp/python/{_PY_VERSION}/python-{_PY_VERSION}-embed-amd64.zip"
_GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

# Dirs/archivos a excluir al empaquetar el backend
_SKIP_BACKEND = {
    "__pycache__", ".venv", "venv", "env",
    ".git", ".mypy_cache", ".pytest_cache",
    "ciudad.db",
    "*.pyc", "*.pyo", "*.egg-info", "dist", "build",
}


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers de empaquetado básico
# ═══════════════════════════════════════════════════════════════════════════════

def _skip(rel: Path, excluir: set) -> bool:
    """Devuelve True si alguna parte del path relativo debe excluirse."""
    for parte in rel.parts:
        if parte in excluir or parte.startswith("."):
            return True
    # Extensiones a excluir
    if rel.suffix in (".pyc", ".pyo"):
        return True
    if rel.name.endswith((".db-shm", ".db-wal")):
        return True
    return False


def _add_dir(zf: zipfile.ZipFile, src: Path, arc_prefix: str, excluir: set):
    """Agrega recursivamente src/ al zip bajo arc_prefix/."""
    if not src.exists():
        return
    for item in src.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(src)
        if _skip(rel, excluir):
            continue
        try:
            zf.write(item, f"{arc_prefix}/{rel.as_posix()}")
        except Exception:
            pass


def _add_file_executable(zf: zipfile.ZipFile, arcname: str, contenido: str):
    """Agrega un archivo al ZIP con permisos +x (para scripts shell en Unix)."""
    info = zipfile.ZipInfo(arcname)
    info.external_attr = 0o755 << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    zf.writestr(info, contenido)


# ═══════════════════════════════════════════════════════════════════════════════
#  Export de la DB activa → SQLite portable
# ═══════════════════════════════════════════════════════════════════════════════

# Tablas con flag is_demo propio — se filtran directo por WHERE is_demo = ?
_TABLAS_CON_IS_DEMO = {
    "propiedades", "clientes", "contratos", "pagos", "leads", "refacciones",
}

# Tablas hijas: para preservar la separación de workspaces, hay que filtrar
# por la FK al padre que sí tiene is_demo. clave = nombre tabla; valor = SQL
# WHERE que filtra por la FK correspondiente. Se usa f-string con {qual_padre}.
_TABLAS_FILTRADAS_POR_PADRE = {
    "ajustes_contrato":      ('contrato_id',  'contratos'),
    "propiedad_adjuntos":    ('propiedad_id', 'propiedades'),
    "propiedad_propietarios":('propiedad_id', 'propiedades'),
    "pago_adjuntos":         ('pago_id',      'pagos'),
    "comprobantes":          ('pago_id',      'pagos'),
    "mensajes_conversacion": ('lead_id',      'leads'),
}

# Tablas globales sin concepto de workspace — siempre se exportan completas
# (settings de schema, users de la plataforma, etc.). Cuidado: users incluye
# TODAS las cuentas, también las que no son del workspace que descarga.
_TABLAS_GLOBALES = {"users", "ciudad_settings", "alembic_version"}


def _export_sqlite(sqlite_path: str, is_demo_workspace: bool | None) -> dict:
    """Exporta a SQLite las tablas filtradas por el workspace del usuario.

    Args:
      sqlite_path: ruta del archivo SQLite destino
      is_demo_workspace: True si el usuario es admin_demo (exporta solo demo),
                         False si es usuario real (exporta solo data real),
                         None para exportar TODO sin filtrar (deprecated).

    Devuelve dict {tabla: cantidad_filas_exportadas}.
    """
    ins = sa_inspect(engine)
    schema = CIUDAD_SCHEMA if IS_POSTGRES else None
    tablas_db = ins.get_table_names(schema=schema)

    if os.path.exists(sqlite_path):
        os.unlink(sqlite_path)
    conn = sqlite3.connect(sqlite_path)
    conn.execute("PRAGMA foreign_keys = OFF")

    def _qual(tabla: str) -> str:
        return f'"{CIUDAD_SCHEMA}"."{tabla}"' if IS_POSTGRES else f'"{tabla}"'

    def _where_workspace(tabla: str) -> str:
        """Devuelve cláusula WHERE para aislar el workspace, o '' si no aplica."""
        if is_demo_workspace is None:
            return ""
        flag_sql = "TRUE" if is_demo_workspace else "FALSE"
        if tabla in _TABLAS_CON_IS_DEMO:
            return f" WHERE is_demo = {flag_sql}"
        if tabla in _TABLAS_FILTRADAS_POR_PADRE:
            fk, padre = _TABLAS_FILTRADAS_POR_PADRE[tabla]
            return f" WHERE {fk} IN (SELECT id FROM {_qual(padre)} WHERE is_demo = {flag_sql})"
        # Globales y otras: sin filtro
        return ""

    resumen: dict[str, int] = {}
    with engine.connect() as src:
        for tabla in tablas_db:
            try:
                cols_info = ins.get_columns(tabla, schema=schema)
                col_names = [c["name"] for c in cols_info]
                if not col_names:
                    continue
                cols_ddl = ", ".join(f'"{c}" TEXT' for c in col_names)
                conn.execute(f'CREATE TABLE IF NOT EXISTS "{tabla}" ({cols_ddl})')

                sql = f"SELECT * FROM {_qual(tabla)}{_where_workspace(tabla)}"
                rows = src.execute(text(sql)).fetchall()
                if rows:
                    placeholders = ", ".join(["?"] * len(col_names))
                    conn.executemany(
                        f'INSERT INTO "{tabla}" VALUES ({placeholders})',
                        [tuple(None if v is None else str(v) for v in r) for r in rows],
                    )
                resumen[tabla] = len(rows)
            except Exception as e:
                print(f"[versiones] No se pudo exportar tabla {tabla}: {e}")
                resumen[tabla] = -1

    conn.commit()
    conn.close()
    return resumen


# ═══════════════════════════════════════════════════════════════════════════════
#  Build del frontend (sin Node en el cliente)
# ═══════════════════════════════════════════════════════════════════════════════

def _ensure_frontend_built() -> Path:
    """Devuelve un directorio con el frontend buildeado. Prioridad:

      1. backend/app/static/ (pre-buildeado y commiteado al repo)
         → Usado en producción, donde no hay Node ni el directorio frontend/
      2. frontend/dist/ (si ya está buildeado)
         → Cache del build local
      3. Buildear frontend/dist/ con `npm run build` (si hay Node)
         → Caso dev local cuando se cambió el frontend

    Si no encuentra ninguno, falla con mensaje claro.
    """
    # 1) Frontend pre-buildeado dentro del backend (caso producción)
    if _FRONTEND_PREBUILT.exists() and (_FRONTEND_PREBUILT / "index.html").exists():
        return _FRONTEND_PREBUILT

    # 2) Dist ya generado en frontend/dist
    if _FRONTEND_DIST.exists() and (_FRONTEND_DIST / "index.html").exists():
        return _FRONTEND_DIST

    # 3) Intentar buildear con npm
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm or not _FRONTEND_ROOT.exists():
        raise RuntimeError(
            "No se encontró el frontend buildeado. Esperaba uno de:\n"
            f"  · {_FRONTEND_PREBUILT}\n"
            f"  · {_FRONTEND_DIST}\n"
            "Y tampoco hay Node/npm para buildearlo en el servidor. "
            "Corré `npm run build` en frontend/ y commiteá el resultado en "
            "backend/app/static/ (usá scripts/copy_frontend.sh)."
        )

    print(f"[versiones] Buildeando frontend con {npm} (puede tardar ~30s)...")
    if not (_FRONTEND_ROOT / "node_modules").exists():
        subprocess.run([npm, "install", "--silent"],
                       cwd=str(_FRONTEND_ROOT), check=True, timeout=300)

    subprocess.run([npm, "run", "build"],
                   cwd=str(_FRONTEND_ROOT), check=True, timeout=300)

    if not _FRONTEND_DIST.exists():
        raise RuntimeError("`npm run build` corrió pero no generó dist/")
    return _FRONTEND_DIST


# ═══════════════════════════════════════════════════════════════════════════════
#  Python embebido para Windows (cacheado)
# ═══════════════════════════════════════════════════════════════════════════════

def _download(url: str, dest: Path):
    """Descarga url → dest. Crea el directorio padre si falta."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": "ciudad-bundler/1.0"})
    with urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def _ensure_python_embedded_windows() -> Path:
    """Descarga (si falta) y prepara Python embebido para Windows con pip habilitado.
    Devuelve el path al directorio listo para empaquetar.

    Se cachea en _CACHE_PY_WIN para no rebajar en cada generación de ZIP.
    """
    marker = _CACHE_PY_WIN / ".ready"
    if marker.exists() and (_CACHE_PY_WIN / "python.exe").exists():
        return _CACHE_PY_WIN

    print("[versiones] Preparando Python embebido para Windows (cache primer uso)...")
    if _CACHE_PY_WIN.exists():
        shutil.rmtree(_CACHE_PY_WIN, ignore_errors=True)
    _CACHE_PY_WIN.mkdir(parents=True, exist_ok=True)

    # 1) Descargar el ZIP oficial
    zip_path = _CACHE_PY_WIN / "embed.zip"
    _download(_PY_EMBED_URL, zip_path)

    # 2) Extraer
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(_CACHE_PY_WIN)
    zip_path.unlink(missing_ok=True)

    # 3) Habilitar pip: descomentar `import site` en python312._pth
    pth_files = list(_CACHE_PY_WIN.glob("python3*._pth"))
    if pth_files:
        pth = pth_files[0]
        contenido = pth.read_text(encoding="utf-8")
        contenido = contenido.replace("#import site", "import site")
        if "import site" not in contenido:
            contenido += "\nimport site\n"
        pth.write_text(contenido, encoding="utf-8")

    # 4) Bajar get-pip.py — la versión embebida no trae pip por defecto
    get_pip = _CACHE_PY_WIN / "get-pip.py"
    _download(_GET_PIP_URL, get_pip)

    marker.touch()
    return _CACHE_PY_WIN


# ═══════════════════════════════════════════════════════════════════════════════
#  Wheels offline para Windows
# ═══════════════════════════════════════════════════════════════════════════════

def _ensure_wheels_windows() -> Path:
    """Baja todas las dependencias de requirements.txt como wheels Windows
    amd64 + py3.12. Si ya hay cache válida, no rebaja. Devuelve el directorio.

    Usa el pip del servidor para descargar wheels específicas del target
    (Windows amd64), no del host. Las wheels descargadas son binary-only:
    si una dep no tiene wheel para Windows, falla con error claro.
    """
    req_file = _BACKEND_ROOT / "requirements.txt"
    marker = _CACHE_WHEELS_WIN / ".ready"

    # Verificar si la cache sigue válida (mismo hash de requirements.txt)
    import hashlib
    req_hash = hashlib.sha256(req_file.read_bytes()).hexdigest()[:12]
    hash_file = _CACHE_WHEELS_WIN / ".req-hash"

    if marker.exists() and hash_file.exists() and hash_file.read_text().strip() == req_hash:
        return _CACHE_WHEELS_WIN

    print("[versiones] Bajando wheels para Windows (cache primer uso)...")
    if _CACHE_WHEELS_WIN.exists():
        shutil.rmtree(_CACHE_WHEELS_WIN, ignore_errors=True)
    _CACHE_WHEELS_WIN.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "pip", "download",
        "-d", str(_CACHE_WHEELS_WIN),
        "-r", str(req_file),
        "--platform", "win_amd64",
        "--python-version", "312",
        "--implementation", "cp",
        "--abi", "cp312",
        "--only-binary=:all:",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        # Si hay deps sin wheels Windows, lo dejamos como warning — el usuario
        # va a tener que tener internet la primera vez para instalar lo que falte.
        print(f"[versiones] pip download (Windows) terminó con warnings:\n{result.stderr[-2000:]}")

    hash_file.write_text(req_hash)
    marker.touch()
    return _CACHE_WHEELS_WIN


# ═══════════════════════════════════════════════════════════════════════════════
#  Construcción del ZIP final
# ═══════════════════════════════════════════════════════════════════════════════

def _build_zip(version_name: str, sqlite_path: str, tablas: dict) -> bytes:
    """Construye el ZIP autocontenido en memoria y retorna los bytes."""
    p = version_name
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    # ── Preparar componentes (algunos requieren red la primera vez) ──────────
    dist_path = _ensure_frontend_built()       # frontend/dist/

    incluir_runtime_win = True
    py_embed_path = None
    wheels_path = None
    try:
        py_embed_path = _ensure_python_embedded_windows()
        wheels_path   = _ensure_wheels_windows()
    except Exception as e:
        print(f"[versiones] No se pudo preparar runtime Windows: {e}")
        incluir_runtime_win = False

    # ── Scripts de arranque ──────────────────────────────────────────────────

    # INICIAR.bat usa el Python embebido empaquetado. Sin instalar nada.
    bat = rf"""@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title CIUDAD - Version local

echo ============================================================
echo   CIUDAD ^| Version local ({version_name})
echo   No requiere instalar Python ni Node
echo ============================================================
echo.

set PY=runtime-windows\python\python.exe
if not exist "%PY%" (
    echo ERROR: No se encontro el runtime de Python en runtime-windows\python\
    echo.
    echo Si descargaste el ZIP sin la opcion de incluir runtime Windows,
    echo instala Python 3.12+ desde https://www.python.org/downloads/
    echo y volve a correr este script.
    pause
    exit /b 1
)

REM Primera vez: instalar pip y dependencias usando wheels offline
if not exist runtime-windows\.installed (
    echo [1/3] Instalando pip ^(primera vez^)...
    "%PY%" runtime-windows\python\get-pip.py --no-warn-script-location --no-index --find-links=runtime-windows\wheels 2>nul
    if errorlevel 1 (
        echo       Sin wheel local para pip, bajando de internet...
        "%PY%" runtime-windows\python\get-pip.py --no-warn-script-location
    )

    echo [2/3] Instalando dependencias offline...
    "%PY%" -m pip install --no-warn-script-location --no-index --find-links=runtime-windows\wheels -r backend\requirements.txt
    if errorlevel 1 (
        echo       Faltan algunas wheels offline, completando desde internet...
        "%PY%" -m pip install --no-warn-script-location -r backend\requirements.txt
    )
    type nul > runtime-windows\.installed
) else (
    echo [1/3] Dependencias ya instaladas, saltando.
    echo [2/3] OK
)

echo [3/3] Iniciando CIUDAD en http://localhost:8000
echo.
echo  - Para detener: cerra esta ventana
echo  - Si el navegador no abre solo, entra a http://localhost:8000
echo.

REM Abrir navegador despues de 3 seg (en paralelo)
start "" /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8000"

cd backend
"%~dp0%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

pause
"""

    # iniciar.sh asume python3 instalado (Mac/Linux modernos lo tienen).
    sh = f"""#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "============================================================"
echo "  CIUDAD | Version local ({version_name})"
echo "============================================================"
echo ""

# Detectar Python 3
PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
    echo "ERROR: Falta Python 3. Instalalo desde:"
    echo "  Mac:   https://www.python.org/downloads/"
    echo "  Linux: usa el package manager (apt/dnf/pacman/brew)"
    exit 1
fi
echo "Usando Python: $PY"

# Crear venv local en .venv si no existe
if [ ! -d ".venv" ]; then
    echo "[1/3] Creando entorno virtual..."
    "$PY" -m venv .venv
fi

VENV_PY=".venv/bin/python"
[ -f "$VENV_PY" ] || VENV_PY=".venv/Scripts/python.exe"  # Windows-bash fallback

if [ ! -f .venv/.installed ]; then
    echo "[2/3] Instalando dependencias (requiere internet primera vez)..."
    "$VENV_PY" -m pip install --quiet --upgrade pip
    "$VENV_PY" -m pip install --quiet -r backend/requirements.txt
    touch .venv/.installed
fi

echo "[3/3] Iniciando CIUDAD en http://localhost:8000"
echo "  - Para detener: Ctrl+C"
echo ""

# Abrir navegador (en background, despues de 3s)
(
    sleep 3
    if command -v open >/dev/null 2>&1; then open http://localhost:8000
    elif command -v xdg-open >/dev/null 2>&1; then xdg-open http://localhost:8000
    fi
) &

cd backend
"../$VENV_PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
"""

    # ── .env para modo local (SQLite, sin Supabase) ──────────────────────────
    env_backend = """# Configuración local — SQLite, sin Supabase
DATABASE_URL=sqlite:///./ciudad.db
SECRET_KEY=ciudad-local-secret-key-offline
CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000

# Activa el servidor SPA: un único puerto sirve API + UI.
# Solo en modo local — en producción cloud se sirve por separado.
SERVE_FRONTEND=true
"""

    # ── README ───────────────────────────────────────────────────────────────
    resumen_tablas = "\n".join(
        f"  · {t:<30} {n:>6} fila{'s' if n != 1 else ''}"
        for t, n in sorted(tablas.items()) if n > 0
    )

    leeme = f"""CIUDAD — Negocios Inmobiliarios
Versión local generada el {now_str}

═══════════════════════════════════════════════════════════
  INSTRUCCIONES — DOBLE CLIC Y LISTO
═══════════════════════════════════════════════════════════

▶ WINDOWS
  Hacer doble clic en:  INICIAR.bat

  No requiere instalar Python ni Node — todo viene incluido.
  La primera vez tarda ~30 seg en instalar dependencias offline.

▶ MAC
  Abrir Terminal en esta carpeta y ejecutar:
    chmod +x iniciar.sh
    ./iniciar.sh

  Requiere Python 3 (instalado por defecto en macOS 12.3+).
  Si no lo tenés, instalalo desde https://www.python.org/downloads/

═══════════════════════════════════════════════════════════
  ACCESO
═══════════════════════════════════════════════════════════

  Aplicación completa:  http://localhost:8000
  Salud del backend:    http://localhost:8000/health

  El backend sirve TAMBIÉN el frontend en el mismo puerto.
  No hay que abrir dos URLs ni correr Vite por separado.

═══════════════════════════════════════════════════════════
  BASE DE DATOS
═══════════════════════════════════════════════════════════

  backend/ciudad.db   ← snapshot SQLite con todos los datos
                        exportados al momento de la descarga.

  Los cambios que hagas en local NO se sincronizan con la
  versión en la nube. Para datos actualizados, generá una
  nueva versión desde Herramientas → Versiones local.

═══════════════════════════════════════════════════════════
  TABLAS EXPORTADAS
═══════════════════════════════════════════════════════════

{resumen_tablas}

═══════════════════════════════════════════════════════════
  CONTENIDO DEL PAQUETE
═══════════════════════════════════════════════════════════

  INICIAR.bat            ← arranque para Windows (doble clic)
  iniciar.sh             ← arranque para Mac/Linux
  runtime-windows/       ← Python 3.12 + dependencias offline
                            (sólo se usa en Windows)
  backend/               ← código del servidor
    app/static/          ← frontend ya buildeado
    ciudad.db            ← base de datos SQLite
    requirements.txt
    .env

═══════════════════════════════════════════════════════════
  CIUDAD — Negocios Inmobiliarios · #VIVIRMEJOR
═══════════════════════════════════════════════════════════
"""

    # ── Armar el ZIP ─────────────────────────────────────────────────────────
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:

        # Base de datos SQLite
        zf.write(sqlite_path, f"{p}/backend/ciudad.db")

        # Código fuente del backend
        _add_dir(zf, _BACKEND_ROOT, f"{p}/backend", _SKIP_BACKEND)

        # Frontend buildeado dentro de backend/app/static/
        # (main.py lo monta automáticamente si encuentra ese directorio)
        _add_dir(zf, dist_path, f"{p}/backend/app/static", set())

        # .env local para el backend
        zf.writestr(f"{p}/backend/.env", env_backend)

        # Runtime de Windows (Python embebido + wheels offline)
        if incluir_runtime_win and py_embed_path and wheels_path:
            _add_dir(zf, py_embed_path, f"{p}/runtime-windows/python", set())
            _add_dir(zf, wheels_path, f"{p}/runtime-windows/wheels", set())

        # Scripts de arranque
        zf.writestr(f"{p}/INICIAR.bat", bat)
        _add_file_executable(zf, f"{p}/iniciar.sh", sh)

        # README
        zf.writestr(f"{p}/LEEME.txt", leeme)

    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
#  Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

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
    user=Depends(get_current_user),
):
    """Genera el snapshot ZIP autocontenido del workspace del usuario llamante
    (data demo o data real, según su rol — no se cruzan). Registra la descarga
    y la devuelve como stream. La primera vez puede tardar varios minutos
    (descarga Python embebido y wheels); las siguientes son ~30 seg por cache.
    """
    ts           = datetime.now().strftime("%Y%m%d-%H%M%S")
    version_name = f"ciudad-v{ts}"

    # Aislamiento de workspace: el snapshot solo lleva la data del usuario
    # que lo solicita. admin_demo → solo is_demo=true. Resto → is_demo=false.
    is_demo_workspace = is_demo_user(user)

    # 1. Exportar DB → SQLite temporal, filtrando por workspace
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        sqlite_path = tmp.name

    try:
        tablas = _export_sqlite(sqlite_path, is_demo_workspace=is_demo_workspace)
    except Exception as e:
        try: os.unlink(sqlite_path)
        except OSError: pass
        raise HTTPException(500, f"Error exportando la base de datos: {e}")

    # 2. Generar ZIP en memoria (incluye frontend build, python embed, wheels)
    try:
        zip_bytes = _build_zip(version_name, sqlite_path, tablas)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, f"Error generando el ZIP: {type(e).__name__}: {e}")
    finally:
        try: os.unlink(sqlite_path)
        except OSError: pass

    size_bytes = len(zip_bytes)

    # 3. Registrar en versiones_local (no crítico si falla)
    try:
        ver = models.VersionLocal(
            nombre     = version_name,
            size_bytes = size_bytes,
            tablas     = json.dumps(tablas),
            notas      = None,
        )
        db.add(ver)
        db.commit()
    except Exception:
        db.rollback()

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
