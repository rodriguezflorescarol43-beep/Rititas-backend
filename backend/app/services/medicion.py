"""Medir la IA desde el panel: ¿cuánto acierta, cuánto inventa y cuánto de eso atrapa el verificador?

Se compara la propuesta de una IA con la «verdad» (lo que la persona confirmó leyendo el documento), y se
pone al lado un método SIN IA (el extractor por reglas) como punto de comparación honesto. Los resultados
se guardan para ver la evolución. No se inventa ningún número: si falta algo, ese dato queda vacío.
"""
import json
from typing import Any, Optional

from sqlmodel import Session, select

from ...tools.extractor_reglas import extraer
from ...tools.medir import _norm, comparar
from ..models.entities import MedicionIA
from . import verificador
from .errores import Invalido

MAX_CAMBIOS = 50


def _cambios(nombre: str, valor: Any) -> list[dict]:
    if not isinstance(valor, dict) or not isinstance(valor.get("cambios"), list) or not valor["cambios"]:
        raise Invalido(f"{nombre}: debe ser una propuesta con al menos un cambio.")
    if len(valor["cambios"]) > MAX_CAMBIOS:
        raise Invalido(f"{nombre}: demasiados cambios (máximo {MAX_CAMBIOS}).")
    if not all(isinstance(c, dict) and isinstance(c.get("datos"), dict) for c in valor["cambios"]):
        raise Invalido(f"{nombre}: cada cambio debe traer «datos».")
    return valor["cambios"]


def _resumen(r: dict) -> dict:
    t = r["totales"]
    propuestos = t["correctos"] + t["incorrectos"] + t["inventados"]
    return {
        # Precisión: de todo lo que propuso (incluido lo inventado), cuánto estaba bien.
        "precision": round(t["correctos"] / propuestos, 3) if propuestos else None,
        "cobertura": r["cobertura"], "esperados": t["esperados"],
        "correctos": t["correctos"], "incorrectos": t["incorrectos"], "omitidos": t["omitidos"],
        "inventados": t["inventados"],
    }


def _detector(propuesta: list[dict], verdad: list[dict], documento: verificador.Documento) -> dict:
    """De los datos que la IA puso mal o inventó, ¿cuántos marcó el verificador? ¿Y cuántas falsas alarmas dio?"""
    errores = detectados = correctos = falsas_alarmas = 0
    for i, propuesto in enumerate(propuesta):
        esperado = verdad[i]["datos"] if i < len(verdad) else {}
        evidencia = propuesto.get("evidencia") or {}
        for campo, valor in propuesto["datos"].items():
            if campo.endswith("_id"):
                continue
            cita = evidencia.get(campo)
            marcado = (not cita or documento.buscar(str(cita)) != "encontrada"
                       or verificador.valor_coincide(valor, str(cita)) is False)
            if campo in esperado and _norm(esperado[campo]) == _norm(valor):
                correctos += 1
                falsas_alarmas += marcado
            else:
                errores += 1
                detectados += marcado
    return {"errores": errores, "detectados": detectados, "correctos": correctos, "falsas_alarmas": falsas_alarmas}


def _reglas(verdad: list[dict], texto: str) -> dict:
    """La misma tarea hecha sin IA. Las reglas solo saben leer convocatorias: lo demás queda sin encontrar."""
    cambios = []
    for esperado in verdad:
        if esperado.get("recurso") == "convocatorias":
            cambios.append(extraer(texto, referencias=esperado.get("referencias"))["cambios"][0])
        else:
            cambios.append({"recurso": esperado.get("recurso"), "datos": {}})
    return {"cambios": cambios}


def medir(session: Session, cuerpo: Any) -> dict:
    if not isinstance(cuerpo, dict):
        raise Invalido("Faltan los datos de la medición.")
    propuesta, verdad = cuerpo.get("propuesta"), cuerpo.get("verdad")
    cambios_ia, cambios_verdad = _cambios("La propuesta de la IA", propuesta), _cambios("La verdad", verdad)
    try:
        documento = verificador.preparar(cuerpo.get("texto_fuente"))
    except ValueError as e:
        raise Invalido(str(e)) from e
    nombre = str(cuerpo.get("documento") or propuesta.get("fuente") or "").strip()[:300]
    if not nombre:
        raise Invalido("Escribe el nombre o el enlace del documento que mediste.")

    ia = comparar(propuesta, verdad, por_orden=True)
    resultado = {
        "ia": _resumen(ia),
        "reglas": _resumen(comparar(_reglas(cambios_verdad, cuerpo["texto_fuente"]), verdad, por_orden=True)) if documento else None,
        "verificador": _detector(cambios_ia, cambios_verdad, documento) if documento else None,
        "errores": ia["errores"][:30],
    }
    fila = MedicionIA(documento=nombre, origen=str(propuesta.get("origen") or "")[:120] or None,
                      resultado=json.dumps(resultado, ensure_ascii=False))
    session.add(fila)
    session.commit()
    session.refresh(fila)
    return _salida(fila)


def _salida(fila: MedicionIA) -> dict:
    return {"id": fila.id, "creado_en": fila.creado_en.isoformat(), "documento": fila.documento,
            "origen": fila.origen, **json.loads(fila.resultado)}


def listar(session: Session, limite: int = 30) -> dict:
    """Las mediciones guardadas y el total acumulado de todas (el número para mostrar al jurado)."""
    filas = list(session.exec(select(MedicionIA).order_by(MedicionIA.id.desc()).limit(limite)))
    salidas = [_salida(f) for f in filas]

    def suma(clave: str, campo: str) -> Optional[int]:
        valores = [s[clave][campo] for s in salidas if s.get(clave)]
        return sum(valores) if valores else None

    total = None
    if salidas:
        esperados, correctos = suma("ia", "esperados"), suma("ia", "correctos")
        propuestos = correctos + suma("ia", "incorrectos") + suma("ia", "inventados")
        reglas_esp, reglas_ok = suma("reglas", "esperados"), suma("reglas", "correctos")
        total = {
            "documentos": len(salidas),
            "ia_cobertura": round(correctos / esperados, 3) if esperados else None,
            "ia_precision": round(correctos / propuestos, 3) if propuestos else None,
            "ia_inventados": suma("ia", "inventados"),
            "reglas_cobertura": round(reglas_ok / reglas_esp, 3) if reglas_esp else None,
            "errores": suma("verificador", "errores"),
            "detectados": suma("verificador", "detectados"),
            "falsas_alarmas": suma("verificador", "falsas_alarmas"),
        }
    return {"total": total, "mediciones": salidas}
