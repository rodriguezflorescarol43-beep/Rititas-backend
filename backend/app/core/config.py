"""Configuración central. Todo se puede cambiar con variables de entorno."""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
RAIZ = BACKEND_DIR.parent

DATABASE_URL = os.getenv("GUIA_DB", f"sqlite:///{BACKEND_DIR / 'guia.db'}")
FRONTEND_DIST = Path(os.getenv("GUIA_DIST", RAIZ / "frontend" / "dist"))

# Archivos subidos desde el panel de administración (imágenes y videos).
UPLOADS_DIR = Path(os.getenv("GUIA_UPLOADS", BACKEND_DIR / "uploads"))
LIMITE_IMAGEN = 5 * 1024 * 1024
LIMITE_VIDEO = 40 * 1024 * 1024

# Acceso de administrador: una sola contraseña. Si no se define, se genera una al arrancar.
ADMIN_PASSWORD_ENV = os.getenv("GUIA_ADMIN_PASSWORD")
SECRETO_ENV = os.getenv("GUIA_SECRET")
TOKEN_HORAS = 8
