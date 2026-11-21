"""Firma digital del paquete de datos (ECDSA P-256).

El servidor firma el paquete con una clave privada y publica la clave pública. Quien reciba el
archivo (por ejemplo por WhatsApp) comprueba la firma en su celular: si alguien cambió una sola
cifra, la firma deja de coincidir y la página lo rechaza.

La clave privada sale de `GUIA_CLAVE_FIRMA` (texto PEM) o de `backend/clave_firma.pem`, que se
crea sola la primera vez y NO debe subirse a Git.
"""
import base64
import os
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from .config import BACKEND_DIR

RUTA_CLAVE = Path(os.getenv("GUIA_RUTA_CLAVE", BACKEND_DIR / "clave_firma.pem"))
_clave: Optional[ec.EllipticCurvePrivateKey] = None


def reiniciar() -> None:
    global _clave
    _clave = None


def _cargar() -> ec.EllipticCurvePrivateKey:
    global _clave
    if _clave is not None:
        return _clave
    pem = os.getenv("GUIA_CLAVE_FIRMA")
    if pem:
        _clave = serialization.load_pem_private_key(pem.encode(), password=None)
    elif RUTA_CLAVE.exists():
        _clave = serialization.load_pem_private_key(RUTA_CLAVE.read_bytes(), password=None)
    else:
        _clave = ec.generate_private_key(ec.SECP256R1())
        RUTA_CLAVE.write_bytes(
            _clave.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        try:
            os.chmod(RUTA_CLAVE, 0o600)
        except OSError:
            pass
    return _clave


def _b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode()


def firmar(datos: bytes) -> str:
    """Firma en formato r||s (64 bytes), que es el que entiende Web Crypto en el navegador."""
    r, s = decode_dss_signature(_cargar().sign(datos, ec.ECDSA(hashes.SHA256())))
    return _b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def clave_publica() -> str:
    """Clave pública en formato SPKI/DER codificada en base64."""
    return _b64(
        _cargar().public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
