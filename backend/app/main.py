"""Punto de entrada. Sirve la API en /api y, si existe, el frontend compilado (PWA)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import admin, catalogo, orientacion
from .core import security
from .core.config import FRONTEND_DIST, UPLOADS_DIR
from .core.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if security.PASSWORD_GENERADA:
        print(
            f"[admin] No hay GUIA_ADMIN_PASSWORD: contraseña temporal de esta sesión = {security.ADMIN_PASSWORD}",
            flush=True,
        )
    yield


app = FastAPI(title="Guía de ingreso", version="1.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# Comprime las respuestas de texto: en señal lenta cada KB cuenta (el CSS baja de ~294 KB a ~79 KB).
app.add_middleware(GZipMiddleware, minimum_size=500)


@app.middleware("http")
async def cabeceras_de_seguridad(request, call_next):
    respuesta = await call_next(request)
    respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
    return respuesta


app.include_router(catalogo.router, prefix="/api")
app.include_router(orientacion.router, prefix="/api")
app.include_router(admin.router_login, prefix="/api/admin")
app.include_router(admin.router, prefix="/api/admin")

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=UPLOADS_DIR), name="media")


@app.get("/api/salud")
def salud():
    return {"estado": "ok"}


@app.get("/{ruta:path}", include_in_schema=False)
def frontend(ruta: str):
    """Entrega archivos del frontend compilado; cualquier otra ruta abre la app (SPA)."""
    if ruta.startswith("api"):
        raise HTTPException(status_code=404, detail="No encontrado")
    if not FRONTEND_DIST.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend sin compilar. Ejecuta `npm run build` en la carpeta frontend.",
        )
    archivo = (FRONTEND_DIST / ruta).resolve()
    if ruta and archivo.is_file() and FRONTEND_DIST.resolve() in archivo.parents:
        cabeceras = {"Cache-Control": "no-cache"} if archivo.name in ("sw.js", "index.html") else None
        return FileResponse(archivo, headers=cabeceras)
    return FileResponse(FRONTEND_DIST / "index.html", headers={"Cache-Control": "no-cache"})
