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
    agregadas += _relajar_obligatorias(motor)
    return agregadas


def _relajar_obligatorias(motor: Engine) -> list[str]:
    """Si una columna pasó de obligatoria a opcional en el modelo, la vuelve opcional en la base.

    SQLite no permite cambiar eso con ALTER, así que se rehace la tabla copiando todos sus datos.
    Ejemplo: la duración de una carrera, que muchas universidades no publican.
    """
    relajadas: list[str] = []
    with motor.begin() as conexion:
        inspector = inspect(conexion)
        for tabla in SQLModel.metadata.sorted_tables:
            if not inspector.has_table(tabla.name):
                continue
            en_base = {c["name"]: c for c in inspector.get_columns(tabla.name)}
            cambiar = [
                c.name for c in tabla.columns
                if c.nullable and not c.primary_key and c.name in en_base and not en_base[c.name]["nullable"]
            ]
            if not cambiar:
                continue
            viejo = f"_viejo_{tabla.name}"
            comunes = ", ".join(f'"{c.name}"' for c in tabla.columns if c.name in en_base)
            for indice in inspector.get_indexes(tabla.name):
                conexion.execute(text(f'DROP INDEX IF EXISTS "{indice["name"]}"'))
            # Sin esto, SQLite reescribiría las referencias de otras tablas hacia el nombre viejo.
            conexion.execute(text("PRAGMA legacy_alter_table = ON"))
            conexion.execute(text(f'ALTER TABLE "{tabla.name}" RENAME TO "{viejo}"'))
            conexion.execute(text("PRAGMA legacy_alter_table = OFF"))
            tabla.create(conexion)
            conexion.execute(text(f'INSERT INTO "{tabla.name}" ({comunes}) SELECT {comunes} FROM "{viejo}"'))
            conexion.execute(text(f'DROP TABLE "{viejo}"'))
            relajadas += [f"{tabla.name}.{c} (ahora opcional)" for c in cambiar]
    return relajadas
