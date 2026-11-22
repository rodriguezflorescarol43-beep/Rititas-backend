"""Mide qué tan bien una propuesta coincide con la «verdad» (lo que anotó una persona).

Sirve para comparar métodos con documentos reales: solo reglas, Claude, otra IA… Se mide por
campo: cuántos acertó, cuántos se equivocó, cuántos no encontró y cuántos inventó.

Uso:  python -m backend.tools.medir propuesta.json verdad.json
"""
import argparse
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any

CLAVES_NOMBRE = ("nombre", "titulo")


def _norm(valor: Any) -> Any:
    if isinstance(valor, bool) or valor is None:
        return valor
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        limpio = unicodedata.normalize("NFD", valor.casefold())
        return " ".join("".join(c for c in limpio if unicodedata.category(c) != "Mn").split())
    return valor


def _clave(cambio: dict) -> tuple:
    datos = cambio.get("datos", {})
    nombre = next((datos[k] for k in CLAVES_NOMBRE if k in datos), None)
    return (cambio.get("recurso"), _norm(nombre) if nombre else cambio.get("id"))


def _es_enlace_interno(campo: str) -> bool:
    return campo.endswith("_id")  # los resuelve el panel a partir de «referencias»


def comparar(propuesta: dict, verdad: dict, por_orden: bool = False) -> dict:
    """`por_orden=True` empareja el cambio N de la propuesta con el cambio N de la verdad (así lo arma el
    panel, que construye la verdad a partir de la propuesta); si no, se emparejan por tipo y nombre."""
    if por_orden:
        obtenidos = {("orden", i): c for i, c in enumerate(propuesta.get("cambios", []))}
        verdad = {**verdad, "cambios": [dict(c, _orden=i) for i, c in enumerate(verdad.get("cambios", []))]}
        clave = lambda c: ("orden", c["_orden"])  # noqa: E731
    else:
        obtenidos = {_clave(c): c for c in propuesta.get("cambios", [])}
        clave = _clave
    esperados_claves = {clave(c) for c in verdad.get("cambios", [])}
    por_campo: dict[str, dict] = {}
    errores: list[dict] = []
    total = dict(esperados=0, correctos=0, incorrectos=0, omitidos=0, inventados=0, con_cita=0, extraidos=0)
    encontrados = 0

    for esperado in verdad.get("cambios", []):
        obtenido = obtenidos.get(clave(esperado))
        if obtenido:
            encontrados += 1
        nombre = esperado["datos"].get("nombre") or esperado["datos"].get("titulo") or esperado.get("id")
        for campo, valor in esperado["datos"].items():
            if _es_enlace_interno(campo):
                continue
            fila = por_campo.setdefault(campo, dict(esperados=0, correctos=0, incorrectos=0, omitidos=0))
            fila["esperados"] += 1
            total["esperados"] += 1
            if obtenido is None or campo not in obtenido.get("datos", {}):
                fila["omitidos"] += 1
                total["omitidos"] += 1
                continue
            total["extraidos"] += 1
            if obtenido.get("evidencia", {}).get(campo):
                total["con_cita"] += 1
            if _norm(obtenido["datos"][campo]) == _norm(valor):
                fila["correctos"] += 1
                total["correctos"] += 1
            else:
                fila["incorrectos"] += 1
                total["incorrectos"] += 1
                errores.append({"cambio": nombre, "campo": campo, "esperado": valor, "obtenido": obtenido["datos"][campo]})
        if obtenido:
            for campo in obtenido["datos"]:
                if campo not in esperado["datos"] and not _es_enlace_interno(campo):
                    total["inventados"] += 1

    return {
        "cambios_esperados": len(esperados_claves),
        "cambios_encontrados": encontrados,
        "cambios_de_mas": len(set(obtenidos) - esperados_claves),
        "totales": total,
        "por_campo": por_campo,
        "cobertura": round(total["correctos"] / total["esperados"], 3) if total["esperados"] else None,
        "precision": round(total["correctos"] / total["extraidos"], 3) if total["extraidos"] else None,
        "con_cita": round(total["con_cita"] / total["extraidos"], 3) if total["extraidos"] else None,
        "errores": errores,
    }


def _porcentaje(x) -> str:
    return "—" if x is None else f"{x * 100:.0f}%"


def informe(r: dict) -> str:
    t = r["totales"]
    lineas = [
        f"Cambios esperados: {r['cambios_esperados']} · encontrados: {r['cambios_encontrados']} · de más: {r['cambios_de_mas']}",
        f"Campos esperados: {t['esperados']} · correctos: {t['correctos']} · incorrectos: {t['incorrectos']} · "
        f"no encontrados: {t['omitidos']} · inventados: {t['inventados']}",
        f"Cobertura (correctos / esperados): {_porcentaje(r['cobertura'])}",
        f"Precisión (correctos / los que propuso): {_porcentaje(r['precision'])}",
        f"Con cita de la fuente: {_porcentaje(r['con_cita'])}",
        "",
        "Por campo:",
    ]
    for campo, f in sorted(r["por_campo"].items()):
        lineas.append(f"  {campo:<24} {f['correctos']}/{f['esperados']} correctos · {f['incorrectos']} mal · {f['omitidos']} sin encontrar")
    if r["errores"]:
        lineas += ["", "Errores:"]
        lineas += [f"  [{e['cambio']}] {e['campo']}: esperado {e['esperado']!r}, obtuvo {e['obtenido']!r}" for e in r["errores"]]
    return "\n".join(lineas)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Compara una propuesta con la verdad anotada por una persona.")
    parser.add_argument("propuesta", type=Path)
    parser.add_argument("verdad", type=Path)
    parser.add_argument("--json", action="store_true", help="imprime el resultado como JSON")
    args = parser.parse_args(argv)
    resultado = comparar(json.loads(args.propuesta.read_text(encoding="utf-8")), json.loads(args.verdad.read_text(encoding="utf-8")))
    print(json.dumps(resultado, ensure_ascii=False, indent=2) if args.json else informe(resultado))
    return 0


if __name__ == "__main__":
    sys.exit(main())
