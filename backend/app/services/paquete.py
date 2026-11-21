"""Capa de negocio: el «paquete de datos», todo el catálogo en una sola respuesta.

Pensado para señal débil: una petición trae todo lo necesario para navegar, ver el estado de las
convocatorias y calcular el test en el celular. Va firmado, así que también se puede compartir
como archivo y comprobar que nadie lo alteró.

El estado de cada convocatoria (abierta, próxima, cerrada) NO viaja en el paquete: se calcula en
el celular con la fecha de hoy, para que nunca quede desactualizado.
"""
import hashlib
import json

from sqlmodel import Session

from ..core import firma
from ..models.entities import AREAS, FACULTADES_TIPO, Ajuste, Carrera, Facultad
from ..repositories import admin as repo_admin
from ..repositories import catalogo as repo
from ..repositories import orientacion as repo_orientacion
from . import admin as servicio_admin
from . import catalogo as servicio_catalogo

FORMATO = 1
VERSION_INICIAL = "1970-01-01T00:00:00Z"


def version_de_datos(session: Session) -> str:
    fila = session.get(Ajuste, "datos_version")
    return fila.valor if fila and fila.valor else VERSION_INICIAL


def _filas(lista) -> list[dict]:
    return [f.model_dump(mode="json") for f in lista]


def construir(session: Session) -> dict:
    preguntas = []
    for pregunta, opciones in repo_orientacion.preguntas_con_opciones(session):
        preguntas.append(
            {
                "id": pregunta.id,
                "texto": pregunta.texto,
                "opciones": [
                    {"id": o.id, "texto": o.texto, "icono": o.icono, "area": o.area} for o in opciones
                ],
            }
        )
    return {
        "version": version_de_datos(session),
        "areas": AREAS,
        "facultades_tipo": FACULTADES_TIPO,
        "departamentos": repo.departamentos(session),
        "ajustes": servicio_admin.leer_ajustes(session),
        "universidades": _filas(repo.listar_universidades(session)),
        "facultades": _filas(repo_admin.listar(session, Facultad)),
        "carreras": _filas(repo_admin.listar(session, Carrera)),
        "convocatorias": _filas(repo.listar_convocatorias(session)),
        "preuniversitarios": _filas(repo.listar_preuniversitarios(session)),
        "embajadores": [e.model_dump(mode="json") for e in servicio_catalogo.listar_embajadores(session)],
        "preguntas": preguntas,
    }


def serializar(datos: dict) -> str:
    """Texto JSON estable: es exactamente lo que se firma y lo que se comprueba."""
    return json.dumps(datos, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def preparar(session: Session) -> dict:
    """Paquete sin firmar. Sirve para calcular la etiqueta sin gastar tiempo en firmar."""
    return {
        "formato": FORMATO,
        "version": version_de_datos(session),
        "datos": serializar(construir(session)),
    }


def con_firma(paquete: dict) -> dict:
    return {**paquete, "firma": firma.firmar(paquete["datos"].encode())}


def etiqueta(paquete: dict) -> str:
    return '"' + hashlib.sha256(paquete["datos"].encode()).hexdigest()[:20] + '"'
