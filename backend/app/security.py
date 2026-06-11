from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import logging
import os
import secrets
from pathlib import Path

from app.database import get_db

logger = logging.getLogger(__name__)

# Raíz del backend (…/app/backend). security.py vive en …/app/backend/app/.
_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _load_secret_key() -> str:
    """Resuelve la SECRET_KEY sin usar NUNCA un string fijo conocido.

    Orden de búsqueda:
      1. Variable de entorno SECRET_KEY (lo normal en producción).
      2. SECRET_KEY definida en el .env del backend (por si load_dotenv
         no corrió todavía o se importó este módulo de forma aislada).
      3. Clave aleatoria persistida en backend/.secret_key (solo dev):
         se genera una vez y se reutiliza para no invalidar tokens en
         cada arranque. Se loguea un warning claro.
    """
    key = os.getenv("SECRET_KEY", "").strip()
    if key:
        return key

    # 2) Buscar en el .env del backend sin pisar el entorno actual.
    env_file = _BACKEND_DIR / ".env"
    if env_file.exists():
        try:
            from dotenv import dotenv_values
            key = (dotenv_values(env_file).get("SECRET_KEY") or "").strip()
            if key:
                return key
        except Exception:
            logger.exception("No se pudo leer SECRET_KEY desde %s", env_file)

    # 3) Fallback dev: clave aleatoria persistida en archivo local.
    key_file = _BACKEND_DIR / ".secret_key"
    try:
        if key_file.exists():
            key = key_file.read_text(encoding="utf-8").strip()
            if key:
                logger.warning(
                    "SECRET_KEY no definida en el entorno ni en .env; usando la clave "
                    "aleatoria persistida en %s. Definí SECRET_KEY en producción.",
                    key_file,
                )
                return key
        key = secrets.token_urlsafe(64)
        key_file.write_text(key, encoding="utf-8")
        logger.warning(
            "SECRET_KEY no definida; se generó una clave aleatoria nueva y se persistió "
            "en %s (solo apto para desarrollo). Los tokens emitidos antes quedan "
            "invalidados. Definí SECRET_KEY como variable de entorno en producción.",
            key_file,
        )
        return key
    except OSError:
        logger.exception(
            "No se pudo persistir la SECRET_KEY generada en %s; se usará una clave "
            "efímera (los tokens se invalidan en cada reinicio).", key_file,
        )
        return secrets.token_urlsafe(64)


SECRET_KEY = _load_secret_key()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _truncate72(p: str) -> bytes:
    """bcrypt acepta máximo 72 bytes; passwords más largas hay que truncarlas."""
    return p.encode("utf-8")[:72]


def hash_pw(p: str) -> str:
    return pwd_context.hash(_truncate72(p))


def verify_pw(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_truncate72(plain), hashed)


def create_token(data: dict) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({**data, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)):
    from app.models import User
    cred_exc = HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = int(payload.get("sub"))
    except JWTError:
        raise cred_exc
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise cred_exc
    return user
