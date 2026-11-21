"""Capa de negocio del panel de administración: altas, cambios y bajas con sus reglas."""
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlmodel import Session

from ..models.entities import (
    Ajuste,
    Carrera,
    Convocatoria,
    Embajador,
    Facultad,
    Mensaje,
    Media,
    Preuniversitario,
    Universidad,
)
from ..repositories import admin as repo
from ..schemas.admin import (
    CarreraIn,
    ConvocatoriaIn,
    EmbajadorIn,
    FacultadIn,
    PreuniversitarioIn,
    UniversidadIn,
)
from .errores import Conflicto, Invalido, NoEncontrado, RecursoDesconocido


@dataclass
class Recurso:
    modelo: Any
    entrada: type[BaseModel]
    padres: tuple = ()  # (campo, ModeloPadre, etiqueta)
    hijos: tuple = field(default_factory=tuple)  # (ModeloHijo, campo, etiqueta)


RECURSOS: dict[str, Recurso] = {
    "universidades": Recurso(
        Universidad, UniversidadIn,
        hijos=((Facultad, "universidad_id", "facultades"), (Embajador, "universidad_id", "embajadores")),
    ),
    "facultades": Recurso(
        Facultad, FacultadIn,
        padres=(("universidad_id", Universidad, "La universidad"),),
        hijos=((Carrera, "facultad_id", "carreras"), (Convocatoria, "facultad_id", "convocatorias")),
    ),
    "carreras": Recurso(Carrera, CarreraIn, padres=(("facultad_id", Facultad, "La facultad"),)),
    "convocatorias": Recurso(Convocatoria, ConvocatoriaIn, padres=(("facultad_id", Facultad, "La facultad"),)),
    "preuniversitarios": Recurso(Preuniversitario, PreuniversitarioIn),
    "embajadores": Recurso(Embajador, EmbajadorIn, padres=(("universidad_id", Universidad, "La universidad"),)),
}

AJUSTES_MAXIMO = {"portada_titulo": 120, "portada_texto": 300, "portada_imagen": 200, "portada_video": 200}
AJUSTES_POR_DEFECTO = {
    "portada_titulo": "Tu camino a la universidad, claro y sin vueltas",
    "portada_texto": "Fechas, costos y carreras en un solo lugar, aunque vivas lejos de la ciudad. Sin registro.",
    "portada_imagen": "",
    "portada_video": "",
}
_RUTA_MEDIA = re.compile(r"^/media/[A-Za-z0-9_.-]+$")


def _recurso(nombre: str) -> Recurso:
    try:
        return RECURSOS[nombre]
    except KeyError:
        raise RecursoDesconocido(f"No existe el recurso «{nombre}»")


def _validar(r: Recurso, cuerpo: dict) -> dict:
    try:
        return r.entrada.model_validate(cuerpo).model_dump()
    except ValidationError as e:
        partes = []
        for err in e.errors():
            campo = ".".join(str(x) for x in err["loc"]) or "datos"
            partes.append(f"{campo}: {err['msg'].removeprefix('Value error, ')}")
        raise Invalido("; ".join(partes))


def _verificar_padres(session: Session, r: Recurso, datos: dict) -> None:
    for campo, padre, etiqueta in r.padres:
        if repo.obtener(session, padre, datos[campo]) is None:
            raise Invalido(f"{etiqueta} indicada no existe")


def _tocar(session: Session) -> None:
    """Marca que los datos cambiaron: las páginas guardadas en los celulares sabrán que hay una versión nueva."""
    marca = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    repo.guardar_ajuste(session, "datos_version", marca)
    session.commit()


def listar(session: Session, nombre: str) -> list[dict]:
    r = _recurso(nombre)
    return [fila.model_dump() for fila in repo.listar(session, r.modelo)]


def crear(session: Session, nombre: str, cuerpo: dict) -> dict:
    r = _recurso(nombre)
    datos = _validar(r, cuerpo)
    _verificar_padres(session, r, datos)
    resultado = repo.guardar(session, r.modelo(**datos)).model_dump()
    _tocar(session)
    return resultado


def actualizar(session: Session, nombre: str, fila_id: int, cuerpo: dict) -> dict:
    r = _recurso(nombre)
    fila = repo.obtener(session, r.modelo, fila_id)
    if fila is None:
        raise NoEncontrado("Registro no encontrado")
    datos = _validar(r, cuerpo)
    _verificar_padres(session, r, datos)
    for clave, valor in datos.items():
        setattr(fila, clave, valor)
    resultado = repo.guardar(session, fila).model_dump()
    _tocar(session)
    return resultado


def borrar(session: Session, nombre: str, fila_id: int) -> None:
    r = _recurso(nombre)
    fila = repo.obtener(session, r.modelo, fila_id)
    if fila is None:
        raise NoEncontrado("Registro no encontrado")
    for hijo, campo, etiqueta in r.hijos:
        n = repo.contar(session, hijo, campo, fila_id)
        if n:
            raise Conflicto(f"No se puede borrar: tiene {n} {etiqueta}. Bórralas primero.")
    repo.borrar(session, fila)
    _tocar(session)


def resumen(session: Session) -> dict:
    cuentas = {nombre: repo.contar(session, r.modelo) for nombre, r in RECURSOS.items()}
    cuentas["mensajes"] = repo.contar(session, Mensaje)
    cuentas["medios"] = repo.contar(session, Media)
    return cuentas


def mensajes(session: Session) -> list[dict]:
    return [m.model_dump() for m in repo.mensajes(session)]


def borrar_mensaje(session: Session, mensaje_id: int) -> None:
    fila = repo.obtener(session, Mensaje, mensaje_id)
    if fila is None:
        raise NoEncontrado("Mensaje no encontrado")
    repo.borrar(session, fila)


def leer_ajustes(session: Session) -> dict[str, str]:
    valores = dict(AJUSTES_POR_DEFECTO)
    for a in repo.ajustes(session):
        if a.clave in valores:
            valores[a.clave] = a.valor
    return valores


def guardar_ajustes(session: Session, datos: dict[str, Any]) -> dict[str, str]:
    for clave, valor in datos.items():
        if clave not in AJUSTES_MAXIMO:
            raise Invalido(f"Ajuste desconocido: {clave}")
        if not isinstance(valor, str):
            raise Invalido(f"{clave}: debe ser texto")
        if len(valor) > AJUSTES_MAXIMO[clave]:
            raise Invalido(f"{clave}: máximo {AJUSTES_MAXIMO[clave]} caracteres")
        if clave in ("portada_imagen", "portada_video") and valor and not _RUTA_MEDIA.match(valor):
            raise Invalido(f"{clave}: elige un archivo de la biblioteca")
    for clave, valor in datos.items():
        repo.guardar_ajuste(session, clave, valor.strip())
    session.commit()
    _tocar(session)
    return leer_ajustes(session)
