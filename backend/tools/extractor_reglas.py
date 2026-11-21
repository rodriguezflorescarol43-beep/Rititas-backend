"""Extractor de convocatorias SIN IA: busca fechas y montos con reglas (expresiones regulares).

Sirve de punto de comparación honesto frente a una IA («¿cuánto más acierta?») y como plan B gratis
cuando no hay IA disponible. Es simple a propósito: solo propone lo que encuentra con claridad y
cita la frase de donde lo sacó. Lo que no entiende, lo deja fuera (nunca adivina).

Uso:  python -m backend.tools.extractor_reglas convocatoria.pdf --universidad UPE \
          --facultad "Facultad de Ingeniería" --salida propuestas/ingenieria.json
"""
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
_LARGA = re.compile(r"(\d{1,2})\s+de\s+([a-záéíóúñ]+)(?:\s+(?:de|del)\s+(\d{4}))?", re.IGNORECASE)
_NUMERICA = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
_MONTO = re.compile(r"(?:Bs\.?|bolivianos)\s*([0-9]+(?:[.,][0-9]{3})*(?:[.,][0-9]{1,2})?)", re.IGNORECASE)


def leer_texto(ruta: Path) -> str:
    if ruta.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        texto = "\n".join((pagina.extract_text() or "") for pagina in PdfReader(str(ruta)).pages)
        if len(texto.strip()) < 20:
            raise ValueError("El PDF no tiene texto (parece una imagen escaneada). Usa una foto con la IA o escribe el texto.")
        return texto
    return ruta.read_text(encoding="utf-8")


def _fechas(texto: str, anio: int) -> list[dict]:
    encontradas = []
    for m in _LARGA.finditer(texto):
        mes = MESES.get(m.group(2).lower())
        if not mes:
            continue
        supuesta = m.group(3) is None
        try:
            encontradas.append({"fecha": date(int(m.group(3) or anio), mes, int(m.group(1))), "pos": m.start(), "fin": m.end(), "supuesta": supuesta})
        except ValueError:
            continue
    for m in _NUMERICA.finditer(texto):
        try:
            encontradas.append({"fecha": date(int(m.group(3)), int(m.group(2)), int(m.group(1))), "pos": m.start(), "fin": m.end(), "supuesta": False})
        except ValueError:
            continue
    return sorted(encontradas, key=lambda f: f["pos"])


def _cita(texto: str, desde: int, hasta: int) -> str:
    return " ".join(texto[max(0, desde - 40): hasta + 40].split())[:160]


def _despues_de(fechas: list[dict], texto: str, patron: str, cuantas: int, distancia: int = 250, excluir=()) -> list[dict]:
    for m in re.finditer(patron, texto, re.IGNORECASE):
        cercanas = [f for f in fechas if m.start() <= f["pos"] <= m.start() + distancia and f not in excluir]
        if len(cercanas) >= cuantas:
            return cercanas[:cuantas]
    return []


def _monto(texto: str) -> Optional[tuple[int, str]]:
    for palabra in re.finditer(r"inscripci[oó]n|costo|arancel|matr[ií]cula", texto, re.IGNORECASE):
        ventana = texto[max(0, palabra.start() - 120): palabra.end() + 160]
        m = _MONTO.search(ventana)
        if m:
            crudo = m.group(1)
            if re.search(r"[.,]\d{3}$", crudo) or re.search(r"[.,]\d{3}[.,]", crudo):
                crudo = re.sub(r"[.,](?=\d{3}\b)", "", crudo)
            valor = round(float(crudo.replace(",", ".")))
            return valor, " ".join(ventana.split())[:160]
    return None


def extraer(texto: str, anio: Optional[int] = None, referencias: Optional[dict] = None, fuente: Optional[str] = None) -> dict:
    anio = anio or date.today().year
    fechas = _fechas(texto, anio)
    datos: dict = {}
    evidencia: dict = {}
    supuso_anio = False

    inscripcion = _despues_de(fechas, texto, r"inscripci[oó]n(?:es)?", 2)
    if len(inscripcion) == 2:
        inicio, fin = inscripcion
        if inicio["supuesta"] and not fin["supuesta"]:  # «del 10 de enero al 10 de febrero de 2027»
            ajuste = fin["fecha"].year - (1 if inicio["fecha"].month > fin["fecha"].month else 0)
            inicio = {**inicio, "fecha": inicio["fecha"].replace(year=ajuste), "supuesta": False}
        if inicio["fecha"] <= fin["fecha"]:
            datos["inscripcion_inicio"] = inicio["fecha"].isoformat()
            datos["inscripcion_fin"] = fin["fecha"].isoformat()
            evidencia["inscripcion_inicio"] = _cita(texto, inicio["pos"], inicio["fin"])
            evidencia["inscripcion_fin"] = _cita(texto, fin["pos"], fin["fin"])
            supuso_anio |= inicio["supuesta"] or fin["supuesta"]

    examen = _despues_de(fechas, texto, r"examen", 1, 200, excluir=inscripcion)
    if examen:
        datos["fecha_examen"] = examen[0]["fecha"].isoformat()
        evidencia["fecha_examen"] = _cita(texto, examen[0]["pos"], examen[0]["fin"])
        supuso_anio |= examen[0]["supuesta"]

    monto = _monto(texto)
    if monto:
        datos["costo_inscripcion_bs"], evidencia["costo_inscripcion_bs"] = monto

    minuscula = texto.lower()
    if "preuniversitario" in minuscula and "examen" in minuscula:
        datos["modalidad_ingreso"] = "ambos"
    elif "preuniversitario" in minuscula:
        datos["modalidad_ingreso"] = "preuniversitario"
    elif "examen" in minuscula:
        datos["modalidad_ingreso"] = "examen"
    if "modalidad_ingreso" in datos:
        evidencia["modalidad_ingreso"] = "Deducido de las palabras «examen» y «preuniversitario» del documento."

    facultad = (referencias or {}).get("facultad")
    datos["titulo"] = f"Convocatoria de ingreso · {facultad}" if facultad else "Convocatoria de ingreso"
    evidencia["titulo"] = "Título armado por el programa; no viene del documento."

    cambio = {
        "accion": "crear", "recurso": "convocatorias", "datos": datos, "evidencia": evidencia,
        "confianza": "baja" if supuso_anio or len(datos) < 5 else "media",
    }
    if referencias:
        cambio["referencias"] = referencias
    propuesta = {"formato": 1, "origen": "extractor por reglas (sin IA)", "cambios": [cambio]}
    if fuente:
        propuesta["fuente"] = fuente
    return propuesta


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Extrae una propuesta de convocatoria de un PDF o texto, sin IA.")
    parser.add_argument("archivo", type=Path)
    parser.add_argument("--universidad")
    parser.add_argument("--facultad")
    parser.add_argument("--anio", type=int, help="año a usar cuando una fecha no lo trae")
    parser.add_argument("--fuente", help="enlace https de donde sale el documento, o el nombre del archivo")
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args(argv)

    referencias = {k: v for k, v in (("universidad", args.universidad), ("facultad", args.facultad)) if v}
    try:
        texto = leer_texto(args.archivo)
    except (OSError, ValueError) as e:
        print(f"No se pudo leer el documento: {e}", file=sys.stderr)
        return 1
    propuesta = extraer(texto, args.anio, referencias or None, args.fuente or args.archivo.name)
    salida = json.dumps(propuesta, ensure_ascii=False, indent=2)
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(salida, encoding="utf-8")
        encontrados = ", ".join(k for k in propuesta["cambios"][0]["datos"] if k != "titulo") or "nada"
        print(f"Propuesta guardada en {args.salida}. Encontré: {encontrados}.")
    else:
        print(salida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
