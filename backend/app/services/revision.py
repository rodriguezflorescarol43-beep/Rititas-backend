"""El «Detective de datos»: revisa la base y avisa qué conviene mirar primero.

Son REGLAS y ESTADÍSTICA simple (medianas, comparación de nombres). No aprende ni usa IA, y no
envía nada fuera del servidor. Cada aviso trae su motivo y qué hacer, para que la persona decida.
"""
import re
import unicodedata
from datetime import date
from statistics import median
from typing import Optional

from sqlmodel import Session

from ..models.entities import Carrera, Convocatoria, Facultad, Preuniversitario, Universidad
from ..repositories import admin as repo
from . import convocatorias as conv

SEVERIDAD = {"alta": 0, "media": 1, "baja": 2}
PALABRAS_VACIAS = {"de", "la", "el", "los", "las", "del", "y", "en", "para"}
DIAS_VERIFICACION_VIEJA = 90


def _tokens(texto: str) -> set[str]:
    limpio = unicodedata.normalize("NFD", texto.lower())
    limpio = "".join(c for c in limpio if unicodedata.category(c) != "Mn")
    return {t for t in re.findall(r"[a-z0-9]+", limpio) if t not in PALABRAS_VACIAS}


def _parecidos(a: set[str], b: set[str]) -> bool:
    """Dos nombres se consideran parecidos si comparten casi todo, o si uno está contenido en el otro."""
    if not a or not b:
        return False
    comunes = a & b
    if not comunes:
        return False
    menor = a if len(a) <= len(b) else b
    return len(comunes) / len(a | b) >= 0.7 or (len(menor) >= 2 and comunes == menor)


def _atipico(valor: Optional[int], otros: list[int]) -> Optional[str]:
    """Compara con la mediana de los demás: muy por debajo (1/5) o muy por encima (5 veces)."""
    if valor is None or len(otros) < 3:
        return None
    m = median(otros)
    if m <= 0:
        return None
    if valor < m * 0.2:
        return f"Bs {valor} es mucho menos que lo habitual (la mediana es Bs {m:g})."
    if valor > m * 5:
        return f"Bs {valor} es mucho más que lo habitual (la mediana es Bs {m:g})."
    return None


def _h(regla, severidad, recurso, fila_id, titulo, detalle, sugerencia, fecha="9999-12-31") -> dict:
    return {
        "clave": f"{regla}:{recurso}:{fila_id}",
        "regla": regla,
        "severidad": severidad,
        "recurso": recurso,
        "fila_id": fila_id,
        "titulo": titulo,
        "detalle": detalle,
        "sugerencia": sugerencia,
        "_orden": (SEVERIDAD[severidad], fecha, titulo),
    }


def revisar(session: Session, hoy: Optional[date] = None) -> dict:
    hoy = hoy or date.today()
    unis = repo.listar(session, Universidad)
    facs = repo.listar(session, Facultad)
    carreras = repo.listar(session, Carrera)
    convs = repo.listar(session, Convocatoria)
    preus = repo.listar(session, Preuniversitario)
    uni_de = {u.id: u for u in unis}
    fac_de = {f.id: f for f in facs}
    hallazgos: list[dict] = []

    # ---------- convocatorias ----------
    costos_insc = [(c.id, c.costo_inscripcion_bs) for c in convs if c.costo_inscripcion_bs is not None]
    for c in convs:
        f = fac_de[c.facultad_id]
        u = uni_de[f.universidad_id]
        nombre = f"{f.nombre} ({u.sigla})"
        estado = conv.calcular_estado(c.inscripcion_inicio, c.inscripcion_fin, hoy)
        a_cierre = (c.inscripcion_fin - hoy).days
        a_apertura = (c.inscripcion_inicio - hoy).days
        fin = c.inscripcion_fin.isoformat()

        if estado != "cerrada":
            if c.verificado_en is None:
                urgente = (estado == "abierta" and a_cierre <= 7) or (estado == "proxima" and a_apertura <= 14)
                cuando = f"cierra en {a_cierre} días" if estado == "abierta" else f"abre en {a_apertura} días"
                hallazgos.append(_h(
                    "sin_verificar", "alta" if urgente else "media", "convocatorias", c.id,
                    f"Convocatoria sin verificar: {nombre}", f"Está {estado.replace('proxima', 'próxima')} y {cuando}, pero nadie la ha confirmado.",
                    "Confírmala en la fuente oficial y anota la fecha de verificación.", fin,
                ))
            elif (hoy - c.verificado_en).days > DIAS_VERIFICACION_VIEJA:
                hallazgos.append(_h(
                    "verificacion_vieja", "media", "convocatorias", c.id,
                    f"Verificación antigua: {nombre}", f"Se verificó hace {(hoy - c.verificado_en).days} días.",
                    "Vuelve a comprobar las fechas en la fuente oficial.", fin,
                ))
        if c.verificado_en is not None and not c.fuente_url:
            hallazgos.append(_h("fuente_faltante", "baja", "convocatorias", c.id, f"Verificada sin fuente: {nombre}",
                                "Tiene fecha de verificación pero no el enlace de donde salió.", "Agrega el enlace oficial.", fin))
        if (c.inscripcion_fin - c.inscripcion_inicio).days > 120:
            hallazgos.append(_h("fechas_raras", "media", "convocatorias", c.id, f"Inscripción muy larga: {nombre}",
                                f"Dura {(c.inscripcion_fin - c.inscripcion_inicio).days} días.", "Revisa que las fechas de inicio y cierre sean las correctas.", fin))
        if c.fecha_examen:
            if c.fecha_examen < c.inscripcion_inicio:
                hallazgos.append(_h("fechas_raras", "alta", "convocatorias", c.id, f"Examen antes de abrir la inscripción: {nombre}",
                                    "La fecha del examen es anterior al inicio de la inscripción.", "Corrige la fecha del examen o la de inicio.", fin))
            elif c.fecha_examen < c.inscripcion_fin:
                hallazgos.append(_h("fechas_raras", "media", "convocatorias", c.id, f"Examen antes de cerrar la inscripción: {nombre}",
                                    "El examen cae mientras todavía se puede inscribir.", "Confírmalo en la fuente: puede ser correcto.", fin))
            elif (c.fecha_examen - c.inscripcion_fin).days > 365:
                hallazgos.append(_h("fechas_raras", "baja", "convocatorias", c.id, f"Examen muy lejano: {nombre}",
                                    "El examen es más de un año después del cierre.", "Revisa el año de la fecha.", fin))
        if estado == "cerrada" and (hoy - c.inscripcion_fin).days > 365:
            hallazgos.append(_h("antigua", "baja", "convocatorias", c.id, f"Convocatoria cerrada hace más de un año: {nombre}",
                                "Ya no sirve a nadie y ocupa espacio.", "Actualízala con la convocatoria nueva o bórrala.", fin))
        aviso = _atipico(c.costo_inscripcion_bs, [v for i, v in costos_insc if i != c.id])
        if aviso:
            hallazgos.append(_h("costo_atipico", "media", "convocatorias", c.id, f"Costo de inscripción atípico: {nombre}", aviso,
                                "Confirma el monto en la fuente oficial.", fin))

    # ---------- universidades ----------
    for u in unis:
        if u.verificado_en is None:
            hallazgos.append(_h("sin_verificar", "baja", "universidades", u.id, f"Universidad sin verificar: {u.nombre}",
                                "No tiene fecha de verificación.", "Confirma costo y becas en su sitio oficial."))
        elif not u.fuente_url:
            hallazgos.append(_h("fuente_faltante", "baja", "universidades", u.id, f"Verificada sin fuente: {u.nombre}",
                                "Tiene fecha de verificación pero no enlace.", "Agrega el enlace oficial."))
        pares = [x.costo_mensual_bs for x in unis if x.id != u.id and x.tipo == u.tipo and x.costo_mensual_bs is not None]
        aviso = _atipico(u.costo_mensual_bs, pares)
        if aviso:
            hallazgos.append(_h("costo_atipico", "media", "universidades", u.id, f"Costo mensual atípico: {u.nombre}", aviso,
                                "Confirma el monto en su sitio oficial."))
        if u.costo_mensual_bs is not None and u.costo_mensual_bs > 20000:
            hallazgos.append(_h("costo_atipico", "media", "universidades", u.id, f"Costo mensual muy alto: {u.nombre}",
                                f"Bs {u.costo_mensual_bs} al mes parece un error de tecleo.", "Revisa el monto."))
        if not any(f.universidad_id == u.id for f in facs):
            hallazgos.append(_h("sin_hijos", "baja", "universidades", u.id, f"Universidad sin facultades: {u.nombre}",
                                "No aparece en ninguna convocatoria.", "Agrega sus facultades."))

    # ---------- facultades ----------
    for f in facs:
        u = uni_de[f.universidad_id]
        if not any(c.facultad_id == f.id for c in convs):
            hallazgos.append(_h("sin_hijos", "baja", "facultades", f.id, f"Facultad sin convocatoria: {f.nombre} ({u.sigla})",
                                "Quien la abra verá «sin convocatoria».", "Carga su convocatoria cuando la publiquen."))
        if not any(c.facultad_id == f.id for c in carreras):
            hallazgos.append(_h("sin_hijos", "media", "facultades", f.id, f"Facultad sin carreras: {f.nombre} ({u.sigla})",
                                "No tiene carreras, así que nunca saldrá en el test.", "Agrega sus carreras."))

    # ---------- preuniversitarios ----------
    for p in preus:
        if p.verificado_en is None:
            hallazgos.append(_h("sin_verificar", "baja", "preuniversitarios", p.id, f"Preuniversitario sin verificar: {p.nombre}",
                                "No tiene fecha de verificación.", "Confírmalo con la fuente o por llamada."))
        if not p.whatsapp and not p.contacto:
            hallazgos.append(_h("sin_contacto", "media", "preuniversitarios", p.id, f"Sin forma de contacto: {p.nombre}",
                                "Quien lo encuentre no podrá comunicarse.", "Agrega WhatsApp o teléfono."))
        if not p.facultades_tipos:
            hallazgos.append(_h("sin_facultades", "media", "preuniversitarios", p.id, f"No aparece en ninguna facultad: {p.nombre}",
                                "No tiene facultades asignadas.", "Marca las facultades para las que prepara."))
        if p.modalidad != "virtual" and (p.latitud is None or p.longitud is None):
            hallazgos.append(_h("sin_ubicacion", "baja", "preuniversitarios", p.id, f"Sin ubicación: {p.nombre}",
                                "«Cerca de mí» no lo incluirá.", "Agrega latitud y longitud."))
        aviso = _atipico(p.costo_bs, [x.costo_bs for x in preus if x.id != p.id and x.costo_bs is not None])
        if aviso:
            hallazgos.append(_h("costo_atipico", "media", "preuniversitarios", p.id, f"Costo atípico: {p.nombre}", aviso,
                                "Confirma el monto con la fuente."))

    # ---------- posibles duplicados ----------
    def duplicados(filas, clave_grupo, etiqueta, recurso, texto):
        for i, a in enumerate(filas):
            for b in filas[i + 1:]:
                if clave_grupo(a) == clave_grupo(b) and _parecidos(_tokens(texto(a)), _tokens(texto(b))):
                    hallazgos.append(_h("posible_duplicado", "media", recurso, b.id, f"Posible duplicado ({etiqueta})",
                                        f"«{texto(a)}» y «{texto(b)}» se parecen mucho.", "Si son el mismo, deja uno y borra el otro."))

    duplicados(unis, lambda x: x.ciudad, "universidad", "universidades", lambda x: x.nombre)
    duplicados(preus, lambda x: x.ciudad, "preuniversitario", "preuniversitarios", lambda x: x.nombre)
    duplicados(facs, lambda x: x.universidad_id, "facultad", "facultades", lambda x: x.nombre)
    duplicados(carreras, lambda x: x.facultad_id, "carrera", "carreras", lambda x: x.nombre)

    hallazgos.sort(key=lambda h: h["_orden"])
    for h in hallazgos:
        h.pop("_orden")
    resumen = {nivel: sum(1 for h in hallazgos if h["severidad"] == nivel) for nivel in SEVERIDAD}
    return {"generado_en": hoy.isoformat(), "resumen": resumen, "hallazgos": hallazgos}
