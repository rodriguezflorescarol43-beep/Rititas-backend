"""Seguridad del panel de administración: contraseña, token firmado y límite de intentos.

No hay cuentas de usuario: existe una sola contraseña de administrador. Si
`GUIA_ADMIN_PASSWORD` no está definida, se genera una al azar en cada arranque y
se muestra en la consola del servidor.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import Header, HTTPException

from .config import ADMIN_PASSWORD_ENV, SECRETO_ENV, TOKEN_HORAS

PASSWORD_GENERADA = ADMIN_PASSWORD_ENV is None
ADMIN_PASSWORD = ADMIN_PASSWORD_ENV or secrets.token_urlsafe(9)
_SECRETO = (SECRETO_ENV or secrets.token_hex(32)).encode()


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def _firma(cuerpo: str) -> str:
    return _b64(hmac.new(_SECRETO, cuerpo.encode(), hashlib.sha256).digest())


def crear_token(ahora: Optional[float] = None) -> tuple[str, int]:
    expira = int((ahora if ahora is not None else time.time()) + TOKEN_HORAS * 3600)
    cuerpo = _b64(json.dumps({"exp": expira}).encode())
    return f"{cuerpo}.{_firma(cuerpo)}", expira


def token_valido(token: str, ahora: Optional[float] = None) -> bool:
    try:
        cuerpo, firma = token.split(".", 1)
        if not hmac.compare_digest(firma, _firma(cuerpo)):
            return False
        relleno = "=" * (-len(cuerpo) % 4)
        expira = json.loads(base64.urlsafe_b64decode(cuerpo + relleno))["exp"]
    except (ValueError, KeyError, TypeError):
        return False
    return (ahora if ahora is not None else time.time()) < expira


def contrasena_correcta(candidata: str) -> bool:
    return hmac.compare_digest(candidata.encode(), ADMIN_PASSWORD.encode())


class LimiteIntentos:
    """Máximo de intentos fallidos por clave (por ejemplo, la IP) en una ventana de tiempo."""

    def __init__(self, maximo: int = 5, ventana_s: int = 60):
        self.maximo = maximo
        self.ventana_s = ventana_s
        self._fallos: dict[str, deque] = defaultdict(deque)

    def _purgar(self, clave: str, ahora: float) -> deque:
        fallos = self._fallos[clave]
        while fallos and ahora - fallos[0] > self.ventana_s:
            fallos.popleft()
        return fallos

    def bloqueado(self, clave: str, ahora: Optional[float] = None) -> bool:
        return len(self._purgar(clave, ahora if ahora is not None else time.time())) >= self.maximo

    def registrar_fallo(self, clave: str, ahora: Optional[float] = None) -> None:
        ahora = ahora if ahora is not None else time.time()
        self._purgar(clave, ahora).append(ahora)

    def limpiar(self, clave: str) -> None:
        self._fallos.pop(clave, None)

    def reiniciar(self) -> None:
        self._fallos.clear()


limite_login = LimiteIntentos()


def requerir_admin(authorization: Optional[str] = Header(default=None)) -> None:
    """Dependencia de FastAPI: exige `Authorization: Bearer <token>` válido."""
    if not authorization or not authorization.startswith("Bearer ") or not token_valido(authorization[7:]):
        raise HTTPException(
            status_code=401,
            detail="Necesitas iniciar sesión como administrador",
            headers={"WWW-Authenticate": "Bearer"},
        )
