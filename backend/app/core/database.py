"""Capa de infraestructura: motor y sesiones de SQLite."""
from sqlmodel import Session, SQLModel, create_engine

from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    from ..models import entities  # noqa: F401  (registra las tablas)

    SQLModel.metadata.create_all(engine)
    from .migraciones import migrar

    migrar(engine)  # agrega columnas nuevas a tablas existentes, sin borrar nada


def get_session():
    with Session(engine) as session:
        yield session
