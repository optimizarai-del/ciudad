"""
Cifrado simétrico para secretos guardados en la base (ej. contraseña web de
Tokko en Conexiones). No guardamos secretos en texto plano.

La clave Fernet se deriva de SECRET_KEY (SHA-256 → base64 urlsafe), así no hay
que administrar una llave aparte. Si SECRET_KEY cambia, los secretos viejos no
se pueden descifrar (hay que recargarlos): es el trade-off aceptable para no
sumar otra variable de entorno.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.security import SECRET_KEY

_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest())
    return Fernet(key)


def cifrar(texto: str | None) -> str | None:
    """Devuelve el texto cifrado (con prefijo de versión) o None si vacío."""
    if not texto:
        return None
    token = _fernet().encrypt(texto.encode()).decode()
    return _PREFIX + token


def descifrar(valor: str | None) -> str | None:
    """Descifra un valor guardado. Tolerante: si viene vacío o no se puede
    descifrar (clave cambiada / dato corrupto), devuelve None sin romper."""
    if not valor:
        return None
    token = valor[len(_PREFIX):] if valor.startswith(_PREFIX) else valor
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, Exception):
        return None
