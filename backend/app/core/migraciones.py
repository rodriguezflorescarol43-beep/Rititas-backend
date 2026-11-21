"""Migración automática mínima para SQLite.

`create_all` crea tablas que faltan, pero no agrega columnas nuevas a tablas que ya existen.
Aquí se agregan esas columnas con `ALTER TABLE ... ADD COLUMN`. Solo agrega: nunca borra ni
cambia datos, así que lo cargado desde el panel de administración se conserva.
"""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel


def _literal(valor) -> str:
    if isinstance(valor, bool):
        return "1" if valor else "0"
    if isinstance(valor, (int, float)):
        return str(valor)
    return "'" + str(valor).replace("'", "''") + "'"


def migrar(motor: Engine) -> list[str]:
    """Devuelve la lista de columnas agregadas, por ejemplo ['preuniversitario.zona']."""
    agregadas: list[str] = []
    inspector = inspect(motor)
    with motor.begin() as conexion:
        for tabla in SQLModel.metadata.sorted_tables:
            if not inspector.has_table(tabla.name):
                continue
            existentes = {c["name"] for c in inspector.get_columns(tabla.name)}
            for columna in tabla.columns:
                if columna.name in existentes:
                    continue
                tipo = columna.type.compile(motor.dialect)
                defecto = ""
                if columna.default is not None and getattr(columna.default, "is_scalar", False):
                    defecto = f" DEFAULT {_literal(columna.default.arg)}"
                elif not columna.nullable:
                    raise RuntimeError(
                        f"La columna nueva {tabla.name}.{columna.name} es obligatoria y no tiene valor "
                        "por defecto: hazla opcional o dale un valor por defecto."
                    )
                nulo = "" if columna.nullable else " NOT NULL"
                conexion.execute(text(f'ALTER TABLE "{tabla.name}" ADD COLUMN "{columna.name}" {tipo}{nulo}{defecto}'))
                agregadas.append(f"{tabla.name}.{columna.name}")
    return agregadas
