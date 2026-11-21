"""Capa de API: test de orientación y formulario de contacto."""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..core.database import get_session
from ..repositories import mensajes as repo_mensajes
from ..schemas import (
    MensajeIn,
    MensajeOut,
    OrientacionIn,
    OrientacionOut,
    PreguntaOut,
)
from ..services import orientacion as servicio

router = APIRouter()


@router.get("/orientacion/preguntas", response_model=list[PreguntaOut])
def preguntas(session: Session = Depends(get_session)):
    return servicio.preguntas(session)


@router.post("/orientacion/resultado", response_model=OrientacionOut)
def resultado(datos: OrientacionIn, session: Session = Depends(get_session)):
    try:
        return servicio.evaluar(session, datos)
    except servicio.RespuestasInvalidas as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/contacto", response_model=MensajeOut, status_code=201)
def contacto(datos: MensajeIn, session: Session = Depends(get_session)):
    fila = repo_mensajes.crear_mensaje(session, datos.nombre, datos.email, datos.mensaje)
    return MensajeOut(id=fila.id, nombre=fila.nombre)
