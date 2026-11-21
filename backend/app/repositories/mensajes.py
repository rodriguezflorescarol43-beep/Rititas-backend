"""Capa de datos: mensajes del formulario de contacto."""
from sqlmodel import Session

from ..models.entities import Mensaje


def crear_mensaje(session: Session, nombre: str, email: str, mensaje: str) -> Mensaje:
    fila = Mensaje(nombre=nombre, email=email, mensaje=mensaje)
    session.add(fila)
    session.commit()
    session.refresh(fila)
    return fila
