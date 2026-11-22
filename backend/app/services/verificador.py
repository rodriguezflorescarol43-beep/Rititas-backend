"""Verificador de citas: revisa si lo que dice la IA está de verdad en el documento oficial.

Una IA puede inventar un dato y también inventar la «cita» que lo respalda (alucinación). Aquí, sin IA y
sin enviar nada fuera del servidor, se comprueba cada cita contra el texto del documento:

- encontrada:    la frase aparece en el documento (sin importar mayúsculas, acentos ni signos).
- parecida:      casi todas sus palabras están en el documento, pero no la frase exacta.
- no_encontrada: la frase no está en el documento → posible dato inventado.

Además se mira si el VALOR coincide con su cita: si la IA dice «Bs 150» pero la cita dice «Bs 200», o la
fecha no aparece en la frase, se avisa. Son reglas simples y explicables: la persona decide.
"""
import re
import unicodedata
from typing import Any, Optional

MAX_TEXTO = 300_000
UMBRAL_PARECIDA = 0.8
MESES = {
    1: ("enero",), 2: ("febrero",), 3: ("marzo",), 4: ("abril",), 5: ("mayo",), 6: ("junio",),
    7: ("julio",), 8: ("agosto",), 9: ("septiembre", "setiembre"), 10: ("octubre",), 11: ("noviembre",),
    12: ("diciembre",),
}
_FECHA_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def normalizar(texto: Any) -> str:
    """Minúsculas, sin acentos y solo letras y números separados por un espacio."""
    limpio = unicodedata.normalize("NFD", str(texto or "").casefold())
    limpio = "".join(c for c in limpio if unicodedata.category(c) != "Mn")
    return " ".join(re.findall(r"[a-z0-9]+", limpio))


class Documento:
    """El texto del documento oficial, preparado una sola vez para buscar muchas citas."""

    def __init__(self, texto: str):
        self.normal = f" {normalizar(texto)} "
        self.palabras = set(self.normal.split())

    def buscar(self, cita: str) -> str:
        frase = normalizar(cita)
        if not frase:
            return "no_encontrada"
        if f" {frase} " in self.normal:
            return "encontrada"
        # Un número cambiado («25» en vez de «20») es justo el invento más peligroso: todos deben estar.
        if any(p not in self.palabras for p in frase.split() if p.isdigit()):
            return "no_encontrada"
        palabras = [p for p in frase.split() if len(p) >= 3]
        if len(palabras) >= 3 and sum(p in self.palabras for p in palabras) / len(palabras) >= UMBRAL_PARECIDA:
            return "parecida"
        return "no_encontrada"


def _sin_separador_de_miles(texto: str) -> str:
    return re.sub(r"(?<=\d)[.,](?=\d{3}\b)", "", texto)


def valor_coincide(valor: Any, cita: Optional[str]) -> Optional[bool]:
    """¿El número o la fecha propuestos aparecen en su cita? None si no se puede saber (textos, listas…)."""
    if not cita or valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        numero = int(valor) if float(valor).is_integer() else valor
        return re.search(rf"(?<![\d.,]){re.escape(str(numero))}(?!\d)", _sin_separador_de_miles(cita)) is not None
    fecha = _FECHA_ISO.match(str(valor))
    if fecha:
        anio, mes, dia = (int(x) for x in fecha.groups())
        palabras = normalizar(cita).split()
        tiene_dia = str(dia) in {p.lstrip("0") for p in palabras}
        tiene_mes = any(nombre in palabras for nombre in MESES[mes]) or re.search(
            rf"(?<!\d)0?{dia}\s+0?{mes}(?!\d)", " ".join(palabras)) is not None
        anios = {int(p) for p in palabras if re.fullmatch(r"20\d{2}", p)}
        anio_bien = not anios or anio in anios  # si la cita no trae año, no se puede contradecir
        return tiene_dia and tiene_mes and anio_bien
    return None


def preparar(texto: Any) -> Optional[Documento]:
    """None si no hay texto (no se puede verificar). Error si no es texto o es demasiado largo."""
    if texto is None or (isinstance(texto, str) and not texto.strip()):
        return None
    if not isinstance(texto, str):
        raise ValueError("«texto_fuente» debe ser texto.")
    if len(texto) > MAX_TEXTO:
        raise ValueError(f"El texto del documento es demasiado largo (máximo {MAX_TEXTO} caracteres).")
    return Documento(texto)
