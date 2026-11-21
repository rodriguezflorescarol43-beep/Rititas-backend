from datetime import date

from backend.app.schemas import ConvocatoriaOut
from backend.app.services.convocatorias import calcular_estado, estado_resumen

HOY = date(2026, 11, 21)


def test_abierta_en_el_rango():
    assert calcular_estado(date(2026, 11, 1), date(2026, 12, 1), HOY) == "abierta"


def test_abierta_el_primer_y_el_ultimo_dia():
    assert calcular_estado(HOY, date(2026, 12, 1), HOY) == "abierta"
    assert calcular_estado(date(2026, 11, 1), HOY, HOY) == "abierta"


def test_proxima_antes_del_inicio():
    assert calcular_estado(date(2026, 12, 1), date(2026, 12, 20), HOY) == "proxima"


def test_cerrada_despues_del_fin():
    assert calcular_estado(date(2026, 10, 1), date(2026, 11, 20), HOY) == "cerrada"


def _c(estado):
    return ConvocatoriaOut(
        id=1, facultad_id=1, titulo="t", inscripcion_inicio=HOY, inscripcion_fin=HOY,
        modalidad_ingreso="ambos", estado=estado,
    )


def test_resumen_prefiere_abierta_luego_proxima():
    assert estado_resumen([_c("cerrada"), _c("abierta"), _c("proxima")]) == "abierta"
    assert estado_resumen([_c("cerrada"), _c("proxima")]) == "proxima"
    assert estado_resumen([]) is None
