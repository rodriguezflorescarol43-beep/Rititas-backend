"""Capa de datos: preguntas del test y carreras por área."""
from sqlmodel import Session, select

from ..models.entities import Carrera, Facultad, Opcion, Pregunta, Universidad


def preguntas_con_opciones(session: Session) -> list[tuple[Pregunta, list[Opcion]]]:
    preguntas = list(session.exec(select(Pregunta).order_by(Pregunta.orden)))
    resultado = []
    for p in preguntas:
        opciones = list(session.exec(select(Opcion).where(Opcion.pregunta_id == p.id)))
        resultado.append((p, opciones))
    return resultado


def opciones_por_ids(session: Session, ids: list[int]) -> list[Opcion]:
    if not ids:
        return []
    return list(session.exec(select(Opcion).where(Opcion.id.in_(ids)).order_by(Opcion.id)))


def carreras_por_areas(
    session: Session, areas: list[str]
) -> list[tuple[Carrera, Facultad, Universidad]]:
    q = (
        select(Carrera, Facultad, Universidad)
        .join(Facultad, Carrera.facultad_id == Facultad.id)
        .join(Universidad, Facultad.universidad_id == Universidad.id)
        .where(Carrera.area.in_(areas))
        .order_by(Carrera.id)
    )
    return [tuple(fila) for fila in session.exec(q)]
