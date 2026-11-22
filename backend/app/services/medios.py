"""Capa de negocio: imágenes y videos subidos por el administrador.

Seguridad: el tipo se decide por los primeros bytes del archivo (nunca por el nombre
ni por lo que declare el navegador), el nombre guardado es aleatorio y no se aceptan
formatos que puedan ejecutar código (por ejemplo SVG o HTML).
"""
import re
import uuid
from pathlib import Path
from typing import Optional

from sqlmodel import Session

from ..core.config import LIMITE_IMAGEN, LIMITE_VIDEO, UPLOADS_DIR
from ..models.entities import Ajuste, Facultad, Media, Preuniversitario, Universidad
from ..repositories import admin as repo
from ..schemas.admin import MediaOut
from sqlmodel import select
from .errores import ArchivoInvalido, Conflicto, NoEncontrado

MARCAS_MP4 = {b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"dash", b"M4V "}
PERMITIDOS = "PNG, JPG, WEBP, GIF, MP4 o WEBM"


def detectar(cabecera: bytes) -> Optional[tuple[str, str, str]]:
    """Devuelve (tipo, mime, extensión) según los primeros bytes, o None si no se permite."""
    if cabecera.startswith(b"\x89PNG\r\n\x1a\n"):
        return "imagen", "image/png", ".png"
    if cabecera.startswith(b"\xff\xd8\xff"):
        return "imagen", "image/jpeg", ".jpg"
    if cabecera[:6] in (b"GIF87a", b"GIF89a"):
        return "imagen", "image/gif", ".gif"
    if cabecera[:4] == b"RIFF" and cabecera[8:12] == b"WEBP":
        return "imagen", "image/webp", ".webp"
    if cabecera[4:8] == b"ftyp" and cabecera[8:12] in MARCAS_MP4:
        return "video", "video/mp4", ".mp4"
    if cabecera.startswith(b"\x1a\x45\xdf\xa3"):
        return "video", "video/webm", ".webm"
    return None


def url_de(m: Media) -> str:
    return f"/media/{m.archivo}"


def a_salida(m: Media) -> MediaOut:
    return MediaOut(
        id=m.id, nombre=m.nombre, archivo=m.archivo, url=url_de(m), tipo=m.tipo,
        mime=m.mime, tamano_bytes=m.tamano_bytes, creado_en=m.creado_en,
    )


def guardar(session: Session, nombre_original: str, contenido: bytes) -> Media:
    if not contenido:
        raise ArchivoInvalido("El archivo está vacío")
    detectado = detectar(contenido[:16])
    if detectado is None:
        raise ArchivoInvalido(f"Formato no permitido. Usa {PERMITIDOS}.", 415)
    tipo, mime, extension = detectado
    limite = LIMITE_IMAGEN if tipo == "imagen" else LIMITE_VIDEO
    if len(contenido) > limite:
        raise ArchivoInvalido(f"El {tipo} supera el máximo de {limite // (1024 * 1024)} MB", 413)

    carpeta = Path(UPLOADS_DIR)
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo = f"{uuid.uuid4().hex}{extension}"
    (carpeta / archivo).write_bytes(contenido)

    nombre = re.sub(r"[^\w .()-]", "_", Path(nombre_original).name)[:80] or archivo
    return repo.guardar(
        session, Media(nombre=nombre, archivo=archivo, tipo=tipo, mime=mime, tamano_bytes=len(contenido))
    )


def en_uso(session: Session, m: Media) -> bool:
    url = url_de(m)
    for modelo, columna in (
        (Universidad, Universidad.imagen_url),
        (Preuniversitario, Preuniversitario.imagen_url),
        (Facultad, Facultad.convocatoria_imagen_url),
    ):
        if session.exec(select(modelo).where(columna == url)).first():
            return True
    return session.exec(select(Ajuste).where(Ajuste.valor == url)).first() is not None


def borrar(session: Session, media_id: int) -> None:
    m = repo.obtener(session, Media, media_id)
    if m is None:
        raise NoEncontrado("Archivo no encontrado")
    if en_uso(session, m):
        raise Conflicto("Este archivo está en uso. Quítalo de la universidad o de la portada primero.")
    carpeta = Path(UPLOADS_DIR).resolve()
    ruta = (carpeta / m.archivo).resolve()
    if carpeta in ruta.parents and ruta.is_file():
        ruta.unlink()
    repo.borrar(session, m)
