"""Capa de negocio: el estado de una convocatoria se calcula con la fecha de hoy."""
from datetime import date
from typing import Optional

from ..models.entities import Convocatoria
from ..schemas import ConvocatoriaOut

ORDEN_ESTADO = {"abierta": 0, "proxima": 1, "cerrada": 2}


def calcular_estado(inicio: date, fin: date, hoy: Optional[date] = None) -> str:
    hoy = hoy or date.today()
    if hoy < inicio:
        return "proxima"
    if hoy > fin:
        return "cerrada"
    return "abierta"


def a_salida(c: Convocatoria, hoy: Optional[date] = None) -> ConvocatoriaOut:
    hoy = hoy or date.today()
    estado = calcular_estado(c.inscripcion_inicio, c.inscripcion_fin, hoy)
    if estado == "abierta":
        dias = (c.inscripcion_fin - hoy).days
    elif estado == "proxima":
        dias = (c.inscripcion_inicio - hoy).days
    else:
        dias = None
    salida = ConvocatoriaOut.model_validate(c)
    salida.estado = estado
    salida.dias_restantes = dias
    return salida


def estado_resumen(convocatorias: list[ConvocatoriaOut]) -> Optional[str]:
    """El estado más útil para una familia: abierta, si no próxima, si no cerrada."""
    if not convocatorias:
        return None
    return min((c.estado for c in convocatorias), key=lambda e: ORDEN_ESTADO[e])
