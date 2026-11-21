"""Capa de negocio: el test «¿No sabes qué estudiar?».

Cada opción de respuesta pertenece a un área. Se cuentan las respuestas por área
y se recomiendan carreras de las dos áreas más fuertes, ajustadas a las
condiciones de la persona (presupuesto, departamento, si puede mudarse).
Cada recomendación explica el motivo: no es una caja negra.
"""
from collections import Counter
from datetime import date
from typing import Optional

from sqlmodel import Session

from ..models.entities import AREAS
from ..repositories import catalogo as repo_catalogo
from ..repositories import orientacion as repo
from ..schemas import (
    AreaPuntaje,
    OrientacionIn,
    OrientacionOut,
    PreguntaOut,
    OpcionOut,
    Recomendacion,
)
from . import convocatorias as conv

AVISO = (
    "Esta orientación es una guía inicial, no un diagnóstico. "
    "Conversa con tu familia y con orientadores, y confirma las fechas con la universidad."
)
MAX_RECOMENDACIONES = 6


class RespuestasInvalidas(Exception):
    pass


def preguntas(session: Session) -> list[PreguntaOut]:
    return [
        PreguntaOut(
            id=p.id,
            texto=p.texto,
            opciones=[OpcionOut.model_validate(o) for o in opciones],
        )
        for p, opciones in repo.preguntas_con_opciones(session)
    ]


def _motivo(area_nombre: str, pct: int, costo: Optional[int], datos: OrientacionIn, mudarse: bool) -> str:
    partes = [f"Encaja con tus intereses en {area_nombre} ({pct}% de tus respuestas)."]
    if costo is not None and datos.presupuesto_max_bs is not None:
        partes.append(f"Su costo estimado (Bs {costo} al mes) entra en tu presupuesto.")
    if datos.departamento and not mudarse:
        partes.append(f"Está en {datos.departamento}, donde vives.")
    if mudarse:
        partes.append("Tendrías que mudarte a otra ciudad.")
    return " ".join(partes)


def evaluar(session: Session, datos: OrientacionIn, hoy: Optional[date] = None) -> OrientacionOut:
    opciones = repo.opciones_por_ids(session, datos.opciones)
    if not opciones:
        raise RespuestasInvalidas("No se encontraron respuestas válidas")

    conteo = Counter(o.area for o in opciones)
    total = len(opciones)
    areas = [
        AreaPuntaje(area=a, nombre=AREAS.get(a, a), porcentaje=round(100 * n / total))
        for a, n in conteo.most_common()
    ]
    pct_por_area = {a.area: a.porcentaje for a in areas}
    fuertes = [a.area for a in areas[:2]]

    candidatas = []
    for carrera, facultad, uni in repo.carreras_por_areas(session, fuertes):
        mudarse = bool(datos.departamento) and uni.departamento != datos.departamento
        if mudarse and not datos.puede_mudarse:
            continue
        sobre_presupuesto = (
            datos.presupuesto_max_bs is not None
            and uni.costo_mensual_bs is not None
            and uni.costo_mensual_bs > datos.presupuesto_max_bs
        )
        if sobre_presupuesto:
            continue
        puntaje = pct_por_area[carrera.area] - (15 if mudarse else 0)
        estados = [conv.a_salida(c, hoy) for c in repo_catalogo.convocatorias_de(session, facultad.id)]
        candidatas.append(
            (
                puntaje,
                Recomendacion(
                    carrera_id=carrera.id,
                    carrera=carrera.nombre,
                    facultad_id=facultad.id,
                    facultad=facultad.nombre,
                    universidad=uni.nombre,
                    tipo=uni.tipo,
                    ciudad=uni.ciudad,
                    departamento=uni.departamento,
                    area=carrera.area,
                    area_nombre=AREAS.get(carrera.area, carrera.area),
                    costo_mensual_bs=uni.costo_mensual_bs,
                    requiere_mudarse=mudarse,
                    estado_convocatoria=conv.estado_resumen(estados),
                    motivo=_motivo(
                        AREAS.get(carrera.area, carrera.area),
                        pct_por_area[carrera.area],
                        uni.costo_mensual_bs,
                        datos,
                        mudarse,
                    ),
                ),
            )
        )

    candidatas.sort(key=lambda par: par[0], reverse=True)
    return OrientacionOut(
        areas=areas,
        recomendaciones=[r for _, r in candidatas[:MAX_RECOMENDACIONES]],
        aviso=AVISO,
    )
