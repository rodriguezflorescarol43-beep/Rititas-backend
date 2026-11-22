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

# «Leer con IA» (solo para el administrador). Sin clave, el botón no aparece y se sigue usando Claude a mano.
# La clave gratis se saca en Google AI Studio. Nunca se envía al navegador ni se guarda en la base de datos.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODELO = os.getenv("GEMINI_MODELO", "gemini-3.1-flash-lite")  # Google cambia los nombres: se puede ajustar aquí
# Si el modelo principal no existe o está saturado, se prueban estos en orden. Los «lite» responden en ~3 s; los grandes
# tardan ~30 s y a veces dan «mucha demanda».
GEMINI_RESPALDOS = [m for m in os.getenv("GEMINI_RESPALDOS", "gemini-flash-lite-latest,gemini-3.5-flash,gemini-3.8-flash").split(",") if m]
