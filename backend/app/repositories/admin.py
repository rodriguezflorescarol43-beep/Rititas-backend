"""Capa de datos del panel de administración."""
from typing import Any, Optional

from sqlmodel import Session, func, select

from ..models.entities import Ajuste, Mensaje, Media


def listar(session: Session, modelo) -> list:
    return list(session.exec(select(modelo).order_by(modelo.id)))


def obtener(session: Session, modelo, fila_id: Any) -> Optional[Any]:
    return session.get(modelo, fila_id)


def guardar(session: Session, fila):
    session.add(fila)
    session.commit()
    session.refresh(fila)
    return fila


def borrar(session: Session, fila) -> None:
    session.delete(fila)
    session.commit()


def contar(session: Session, modelo, campo: Optional[str] = None, valor: Any = None) -> int:
    q = select(func.count()).select_from(modelo)
    if campo is not None:
        q = q.where(getattr(modelo, campo) == valor)
    return session.exec(q).one()


def ajustes(session: Session) -> list[Ajuste]:
    return list(session.exec(select(Ajuste)))


def guardar_ajuste(session: Session, clave: str, valor: str) -> None:
    fila = session.get(Ajuste, clave) or Ajuste(clave=clave)
    fila.valor = valor
    session.add(fila)


def mensajes(session: Session) -> list[Mensaje]:
    return list(session.exec(select(Mensaje).order_by(Mensaje.id.desc())))


def medios(session: Session) -> list[Media]:
    return list(session.exec(select(Media).order_by(Media.id.desc())))
