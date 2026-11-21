"""Capa de datos: consultas a SQLite. Aquí no hay reglas de negocio."""
from typing import Optional

from sqlmodel import Session, select

from ..models.entities import (
    Carrera,
    Convocatoria,
    Embajador,
    Facultad,
    Preuniversitario,
    Universidad,
)


def listar_universidades(
    session: Session, tipo: Optional[str] = None, departamento: Optional[str] = None
) -> list[Universidad]:
    q = select(Universidad).order_by(Universidad.nombre)
    if tipo:
        q = q.where(Universidad.tipo == tipo)
    if departamento:
        q = q.where(Universidad.departamento == departamento)
    return list(session.exec(q))


def obtener_universidad(session: Session, universidad_id: int) -> Optional[Universidad]:
    return session.get(Universidad, universidad_id)


def listar_facultades(
    session: Session, universidad_id: Optional[int] = None, area: Optional[str] = None
) -> list[Facultad]:
    q = select(Facultad).order_by(Facultad.nombre)
    if universidad_id:
        q = q.where(Facultad.universidad_id == universidad_id)
    if area:
        q = q.where(Facultad.area == area)
    return list(session.exec(q))


def obtener_facultad(session: Session, facultad_id: int) -> Optional[Facultad]:
    return session.get(Facultad, facultad_id)


def carreras_de(session: Session, facultad_id: int) -> list[Carrera]:
    q = select(Carrera).where(Carrera.facultad_id == facultad_id).order_by(Carrera.nombre)
    return list(session.exec(q))


def convocatorias_de(session: Session, facultad_id: int) -> list[Convocatoria]:
    q = (
        select(Convocatoria)
        .where(Convocatoria.facultad_id == facultad_id)
        .order_by(Convocatoria.inscripcion_inicio)
    )
    return list(session.exec(q))


def listar_convocatorias(session: Session) -> list[Convocatoria]:
    return list(session.exec(select(Convocatoria).order_by(Convocatoria.inscripcion_fin)))


def listar_preuniversitarios(
    session: Session, departamento: Optional[str] = None
) -> list[Preuniversitario]:
    q = select(Preuniversitario).order_by(Preuniversitario.departamento, Preuniversitario.nombre)
    if departamento:
        q = q.where(Preuniversitario.departamento == departamento)
    return list(session.exec(q))


def obtener_preuniversitario(session: Session, preu_id: int) -> Optional[Preuniversitario]:
    return session.get(Preuniversitario, preu_id)


def embajadores_publicos(session: Session) -> list[tuple[Embajador, Universidad]]:
    """Solo quien está activo, es mayor de edad y dio su consentimiento."""
    q = (
        select(Embajador, Universidad)
        .join(Universidad, Embajador.universidad_id == Universidad.id)
        .where(
            Embajador.activo.is_(True),
            Embajador.consentimiento.is_(True),
            Embajador.mayor_de_edad.is_(True),
        )
        .order_by(Universidad.nombre, Embajador.nombre)
    )
    return [tuple(fila) for fila in session.exec(q)]


def departamentos(session: Session) -> list[str]:
    nombres = set(session.exec(select(Universidad.departamento)))
    nombres |= set(session.exec(select(Preuniversitario.departamento)))
    return sorted(nombres)
