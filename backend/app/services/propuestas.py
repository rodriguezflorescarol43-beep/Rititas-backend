"""Importar propuestas: datos sugeridos por una IA (o por una persona) que el administrador revisa.

Una propuesta es un archivo JSON con cambios (crear o actualizar) y la CITA de la fuente de cada
dato. Aquí se analiza (sin escribir nada), se muestra el antes y el después, y solo se aplica lo
que la persona aprueba. La IA no tiene ningún permiso de escritura: todo pasa por las mismas
validaciones de siempre.

Seguridad: solo se pueden tocar datos públicos de fuentes oficiales. Embajadores y mensajes de
contacto (datos personales) quedan fuera a propósito.
"""
import json
import re
import unicodedata
from datetime import date
from typing import Any, Optional

from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlmodel import Session, select

from ..models.entities import Carrera, Convocatoria, Facultad, Preuniversitario, RegistroCambio, Universidad
from ..repositories import admin as repo
from . import admin as servicio_admin
from .errores import Conflicto, Invalido, NoEncontrado

FORMATO = 1
MAX_CAMBIOS = 50
PERMITIDOS = ("universidades", "facultades", "carreras", "convocatorias", "preuniversitarios")
_URL = re.compile(r"^https?://\S+$")


def _norm(texto: Any) -> str:
    limpio = unicodedata.normalize("NFD", str(texto or "").casefold())
    return " ".join("".join(c for c in limpio if unicodedata.category(c) != "Mn").split())


def _json(valor: Any) -> Any:
    return jsonable_encoder(valor)


# ---------- estructura ----------

def _estructura(propuesta: Any) -> list[dict]:
    if not isinstance(propuesta, dict):
        raise Invalido("La propuesta debe ser un objeto JSON.")
    if propuesta.get("formato") != FORMATO:
        raise Invalido(f"Formato no reconocido: se espera «formato»: {FORMATO}.")
    cambios = propuesta.get("cambios")
    if not isinstance(cambios, list) or not cambios:
        raise Invalido("La propuesta no trae cambios.")
    if len(cambios) > MAX_CAMBIOS:
        raise Invalido(f"Demasiados cambios ({len(cambios)}). El máximo por archivo es {MAX_CAMBIOS}.")
    for i, c in enumerate(cambios, start=1):
        if not isinstance(c, dict):
            raise Invalido(f"Cambio {i}: debe ser un objeto.")
        if c.get("accion") not in ("crear", "actualizar"):
            raise Invalido(f"Cambio {i}: «accion» debe ser «crear» o «actualizar».")
        if c.get("recurso") not in PERMITIDOS:
            raise Invalido(f"Cambio {i}: «recurso» debe ser uno de: {', '.join(PERMITIDOS)}.")
        if not isinstance(c.get("datos"), dict) or not c["datos"]:
            raise Invalido(f"Cambio {i}: «datos» debe traer al menos un campo.")
        if c["accion"] == "actualizar" and not isinstance(c.get("id"), int):
            raise Invalido(f"Cambio {i}: para actualizar hace falta el «id» del registro (usa «Descargar referencias»).")
        if not isinstance(c.get("evidencia", {}), dict) or not isinstance(c.get("referencias", {}), dict):
            raise Invalido(f"Cambio {i}: «evidencia» y «referencias» deben ser objetos.")
    return cambios


# ---------- referencias por nombre ----------

def _buscar_universidad(session: Session, texto: str) -> tuple[Optional[int], Optional[str]]:
    clave = _norm(texto)
    unis = repo.listar(session, Universidad)
    exactas = [u for u in unis if clave in (_norm(u.sigla), _norm(u.nombre))]
    if len(exactas) == 1:
        return exactas[0].id, None
    candidatas = exactas or [u for u in unis if clave and clave in _norm(u.nombre)]
    if len(candidatas) == 1:
        return candidatas[0].id, None
    if not candidatas:
        return None, f"No encontré la universidad «{texto}»."
    return None, f"«{texto}» es ambigua: {', '.join(u.sigla for u in candidatas)}."


def _buscar_facultad(session: Session, texto: str, universidad: Optional[str]) -> tuple[Optional[int], Optional[str]]:
    uni_id = None
    if universidad:
        uni_id, error = _buscar_universidad(session, universidad)
        if error:
            return None, error
    clave = _norm(texto)
    facs = [f for f in repo.listar(session, Facultad) if uni_id is None or f.universidad_id == uni_id]
    exactas = [f for f in facs if _norm(f.nombre) == clave]
    candidatas = exactas or [f for f in facs if clave and clave in _norm(f.nombre)]
    if len(candidatas) == 1:
        return candidatas[0].id, None
    if not candidatas:
        return None, f"No encontré la facultad «{texto}»."
    return None, f"La facultad «{texto}» es ambigua; indica también la universidad."


def _resolver_padres(session: Session, recurso: str, referencias: dict, datos: dict) -> list[str]:
    errores: list[str] = []
    if recurso == "facultades" and "universidad_id" not in datos and referencias.get("universidad"):
        valor, error = _buscar_universidad(session, str(referencias["universidad"]))
        (datos.__setitem__("universidad_id", valor) if valor else errores.append(error))
    if recurso in ("carreras", "convocatorias") and "facultad_id" not in datos and referencias.get("facultad"):
        valor, error = _buscar_facultad(session, str(referencias["facultad"]), referencias.get("universidad"))
        (datos.__setitem__("facultad_id", valor) if valor else errores.append(error))
    return errores


# ---------- validación ----------

def _validar(recurso: str, datos: dict) -> tuple[Optional[dict], list[str]]:
    entrada = servicio_admin.RECURSOS[recurso].entrada
    try:
        return entrada.model_validate(datos).model_dump(), []
    except ValidationError as e:
        errores = []
        for err in e.errors():
            campo = ".".join(str(x) for x in err["loc"]) or "datos"
            errores.append(f"{campo}: {err['msg'].removeprefix('Value error, ')}")
        return None, errores


def _titulo(recurso: str, datos: dict) -> str:
    return str(datos.get("nombre") or datos.get("titulo") or recurso)


def _similar_existente(session: Session, recurso: str, datos: dict) -> Optional[Any]:
    modelo = servicio_admin.RECURSOS[recurso].modelo
    clave = _norm(datos.get("nombre") or datos.get("titulo"))
    if not clave:
        return None
    for fila in repo.listar(session, modelo):
        if _norm(getattr(fila, "nombre", None) or getattr(fila, "titulo", None)) == clave:
            padre = next((c for c in ("universidad_id", "facultad_id") if hasattr(fila, c)), None)
            if padre is None or getattr(fila, padre) == datos.get(padre):
                return fila
    return None


def _preparar(session: Session, propuesta: Any, hoy: Optional[date] = None) -> list[dict]:
    hoy = hoy or date.today()
    resultado = []
    for indice, cambio in enumerate(_estructura(propuesta)):
        recurso = cambio["recurso"]
        entrada = servicio_admin.RECURSOS[recurso].entrada
        modelo = servicio_admin.RECURSOS[recurso].modelo
        evidencia = {k: str(v) for k, v in (cambio.get("evidencia") or {}).items()}
        errores: list[str] = []
        advertencias: list[str] = []
        desconocidos = sorted(set(cambio["datos"]) - set(entrada.model_fields))
        if desconocidos:
            advertencias.append(f"Se ignoran campos desconocidos: {', '.join(desconocidos)}.")
        datos = {k: v for k, v in cambio["datos"].items() if k in entrada.model_fields}
        fila_id: Optional[int] = None
        actual: dict = {}

        if cambio["accion"] == "actualizar":
            fila_id = cambio["id"]
            fila = repo.obtener(session, modelo, fila_id)
            if fila is None:
                errores.append(f"No existe el registro {fila_id} en {recurso}.")
            else:
                actual = fila.model_dump()
                actual.pop("id", None)
            propuesto = {**actual, **datos} if fila is not None else None
        else:
            errores += _resolver_padres(session, recurso, cambio.get("referencias") or {}, datos)
            propuesto = datos

        validado = None
        if propuesto is not None and not errores:
            validado, errores_validacion = _validar(recurso, propuesto)
            errores += errores_validacion
            if validado is not None:
                for campo, padre, etiqueta in servicio_admin.RECURSOS[recurso].padres:
                    if repo.obtener(session, padre, validado[campo]) is None:
                        errores.append(f"{etiqueta} indicada no existe.")

        diff = []
        if validado is not None:
            campos_mostrados = list(datos.keys()) + [c for c in ("universidad_id", "facultad_id") if c in validado and c not in datos]
            for campo in campos_mostrados:
                antes = _json(actual.get(campo)) if cambio["accion"] == "actualizar" else None
                despues = _json(validado.get(campo))
                diff.append({"campo": campo, "antes": antes, "despues": despues,
                             "cambia": antes != despues, "evidencia": evidencia.get(campo)})
            sin_cita = [d["campo"] for d in diff if d["cambia"] and not d["evidencia"] and not d["campo"].endswith("_id")]
            if sin_cita:
                advertencias.append(f"Sin cita de la fuente: {', '.join(sin_cita)}.")
            if cambio["accion"] == "actualizar" and not any(d["cambia"] for d in diff):
                advertencias.append("No cambia nada: los datos ya coinciden.")
            if cambio["accion"] == "crear":
                existente = _similar_existente(session, recurso, validado)
                if existente is not None:
                    advertencias.append(f"Ya existe uno con el mismo nombre (id {existente.id}). ¿No será una actualización?")
            if recurso == "convocatorias" and validado["inscripcion_fin"] < hoy:
                advertencias.append("La fecha de cierre ya pasó.")

        resultado.append({
            "indice": indice,
            "accion": cambio["accion"],
            "recurso": recurso,
            "id": fila_id,
            "titulo": _titulo(recurso, {**actual, **datos}),
            "valido": not errores,
            "errores": errores,
            "advertencias": advertencias,
            "diff": diff,
            "confianza": cambio.get("confianza"),
            "_validado": validado,
            "_evidencia": evidencia,
        })
    return resultado


# ---------- API del servicio ----------

def analizar(session: Session, propuesta: Any, hoy: Optional[date] = None) -> dict:
    """Revisa la propuesta SIN escribir nada."""
    preparados = _preparar(session, propuesta, hoy)
    limpios = [{k: v for k, v in p.items() if not k.startswith("_")} for p in preparados]
    return {
        "fuente": propuesta.get("fuente"),
        "origen": propuesta.get("origen"),
        "total": len(limpios),
        "validos": sum(1 for p in limpios if p["valido"]),
        "con_errores": sum(1 for p in limpios if not p["valido"]),
        "cambios": limpios,
    }


def _marcar_verificacion(recurso: str, datos: dict, hoy: date, url: Optional[str]) -> None:
    """Aprobar equivale a que la persona revisó la fuente: se anota la fecha y, si es un enlace, la fuente."""
    campos = servicio_admin.RECURSOS[recurso].entrada.model_fields
    if "verificado_en" in campos:
        datos["verificado_en"] = hoy
    if url and "fuente_url" in campos:
        datos["fuente_url"] = url


def aplicar(session: Session, propuesta: Any, aprobados: Any, hoy: Optional[date] = None) -> dict:
    """Aplica SOLO lo aprobado. Se vuelve a validar todo: nunca se confía en lo que manda el navegador."""
    hoy = hoy or date.today()
    if not isinstance(aprobados, list) or not aprobados:
        raise Invalido("No hay cambios aprobados.")
    preparados = {p["indice"]: p for p in _preparar(session, propuesta, hoy)}
    fuente = propuesta.get("fuente")
    url = fuente if isinstance(fuente, str) and _URL.match(fuente) else None
    aplicados, omitidos = [], []

    for aprobado in aprobados:
        indice = aprobado.get("indice") if isinstance(aprobado, dict) else None
        p = preparados.get(indice)
        if p is None:
            omitidos.append({"indice": indice, "motivo": "No existe ese cambio en la propuesta."})
            continue
        if not p["valido"]:
            omitidos.append({"indice": indice, "motivo": "Tiene errores: " + "; ".join(p["errores"])})
            continue
        recurso, validado = p["recurso"], dict(p["_validado"])
        try:
            if p["accion"] == "crear":
                _marcar_verificacion(recurso, validado, hoy, url)
                resultado = servicio_admin.crear(session, recurso, validado)
                antes, despues = None, {d["campo"]: d["despues"] for d in p["diff"]}
            else:
                pedidos = aprobado.get("campos")
                cambiables = [d["campo"] for d in p["diff"] if d["cambia"]]
                elegidos = cambiables if pedidos is None else [c for c in pedidos if c in cambiables]
                if not elegidos:
                    omitidos.append({"indice": indice, "motivo": "No se eligió ningún campo que cambie."})
                    continue
                fila = repo.obtener(session, servicio_admin.RECURSOS[recurso].modelo, p["id"])
                nuevo = fila.model_dump()
                nuevo.pop("id", None)
                antes = {c: _json(nuevo[c]) for c in elegidos}
                for c in elegidos:
                    nuevo[c] = validado[c]
                _marcar_verificacion(recurso, nuevo, hoy, url)
                resultado = servicio_admin.actualizar(session, recurso, p["id"], nuevo)
                despues = {c: _json(validado[c]) for c in elegidos}
        except (Invalido, NoEncontrado, Conflicto) as e:
            omitidos.append({"indice": indice, "motivo": str(e)})
            continue
        session.add(RegistroCambio(
            recurso=recurso, fila_id=resultado["id"], accion=p["accion"],
            fuente=str(fuente) if fuente else None, origen=propuesta.get("origen"),
            antes=json.dumps(antes, ensure_ascii=False) if antes is not None else None,
            despues=json.dumps(despues, ensure_ascii=False),
            evidencia=json.dumps(p["_evidencia"], ensure_ascii=False),
        ))
        session.commit()
        aplicados.append({"indice": indice, "recurso": recurso, "id": resultado["id"], "accion": p["accion"]})
    return {"aplicados": aplicados, "omitidos": omitidos}


def referencias(session: Session) -> dict:
    """Lista compacta con los números internos, para que una IA o una persona pueda indicar «id» al actualizar."""
    unis = repo.listar(session, Universidad)
    nombre_uni = {u.id: u.sigla for u in unis}
    facs = repo.listar(session, Facultad)
    return {
        "universidades": [{"id": u.id, "sigla": u.sigla, "nombre": u.nombre, "ciudad": u.ciudad} for u in unis],
        "facultades": [{"id": f.id, "nombre": f.nombre, "universidad": nombre_uni[f.universidad_id]} for f in facs],
        "carreras": [{"id": c.id, "nombre": c.nombre, "facultad_id": c.facultad_id} for c in repo.listar(session, Carrera)],
        "convocatorias": [
            {"id": c.id, "titulo": c.titulo, "facultad_id": c.facultad_id,
             "inscripcion_inicio": c.inscripcion_inicio.isoformat(), "inscripcion_fin": c.inscripcion_fin.isoformat()}
            for c in repo.listar(session, Convocatoria)
        ],
        "preuniversitarios": [{"id": p.id, "nombre": p.nombre, "ciudad": p.ciudad} for p in repo.listar(session, Preuniversitario)],
    }


def registro(session: Session, limite: int = 50) -> list[dict]:
    filas = session.exec(select(RegistroCambio).order_by(RegistroCambio.id.desc()).limit(limite))
    salida = []
    for f in filas:
        salida.append({
            "id": f.id, "creado_en": f.creado_en.isoformat(), "recurso": f.recurso, "fila_id": f.fila_id,
            "accion": f.accion, "fuente": f.fuente, "origen": f.origen,
            "antes": json.loads(f.antes) if f.antes else None,
            "despues": json.loads(f.despues) if f.despues else None,
            "evidencia": json.loads(f.evidencia) if f.evidencia else None,
        })
    return salida
