"""Capa de negocio: arma las respuestas del catálogo (universidades, facultades)."""
from datetime import date
from typing import Optional

from sqlmodel import Session

from ..models.entities import AREAS, Facultad
from ..repositories import catalogo as repo
from ..schemas import (
    CarreraOut,
    EmbajadorOut,
    FacultadDetalle,
    FacultadResumen,
    UniversidadOut,
)
from . import convocatorias as conv


class NoEncontrado(Exception):
    pass


def _convocatorias_de(session: Session, facultad_id: int, hoy: Optional[date]):
    return [conv.a_salida(c, hoy) for c in repo.convocatorias_de(session, facultad_id)]


def resumen_facultad(session: Session, f: Facultad, hoy: Optional[date] = None) -> FacultadResumen:
    uni = repo.obtener_universidad(session, f.universidad_id)
    return FacultadResumen(
        id=f.id,
        nombre=f.nombre,
        area=f.area,
        area_nombre=AREAS.get(f.area, f.area),
        universidad_id=uni.id,
        universidad_nombre=uni.nombre,
        universidad_sigla=uni.sigla,
        tipo=uni.tipo,
        ciudad=uni.ciudad,
        departamento=uni.departamento,
        n_carreras=len(repo.carreras_de(session, f.id)),
        estado_convocatoria=conv.estado_resumen(_convocatorias_de(session, f.id, hoy)),
    )


def listar_facultades(session: Session, universidad_id=None, area=None, hoy=None):
    filas = repo.listar_facultades(session, universidad_id, area)
    return [resumen_facultad(session, f, hoy) for f in filas]


def detalle_facultad(session: Session, facultad_id: int, hoy=None) -> FacultadDetalle:
    f = repo.obtener_facultad(session, facultad_id)
    if f is None:
        raise NoEncontrado("Facultad no encontrada")
    base = resumen_facultad(session, f, hoy)
    uni = repo.obtener_universidad(session, f.universidad_id)
    return FacultadDetalle(
        **base.model_dump(),
        universidad=UniversidadOut.model_validate(uni),
        carreras=[CarreraOut.model_validate(c) for c in repo.carreras_de(session, f.id)],
        convocatorias=_convocatorias_de(session, f.id, hoy),
    )


def listar_embajadores(session: Session) -> list[EmbajadorOut]:
    return [
        EmbajadorOut(
            id=e.id,
            nombre=e.nombre,
            universidad_id=u.id,
            universidad_nombre=u.nombre,
            carrera=e.carrera,
            mensaje=e.mensaje,
            whatsapp=e.whatsapp,
        )
        for e, u in repo.embajadores_publicos(session)
    ]


def listar_convocatorias(session: Session, estado: Optional[str] = None, hoy=None):
    salida = [conv.a_salida(c, hoy) for c in repo.listar_convocatorias(session)]
    if estado:
        salida = [c for c in salida if c.estado == estado]
    return salida
