"""Carga datos REALES de Cochabamba (prueba), tomados de las páginas oficiales.

Uso (desde la carpeta del proyecto):
    python -m backend.tools.cargar_cochabamba

Qué hace:
  1. Copia la base actual a backend/guia.respaldo-AAAAMMDD-HHMMSS.db (para volver atrás).
  2. Borra el catálogo de EJEMPLO (universidades, facultades, carreras, convocatorias,
     preuniversitarios y embajadores inventados). No toca el test, la portada, los medios ni los mensajes.
  3. Carga lo encontrado en internet el 22-nov-2026, con el enlace de la fuente.

Reglas que se siguieron:
  - Nada se inventa: si la fuente no lo dice, el campo queda vacío («Por confirmar» en la página).
  - `verificado_en` queda vacío: lo llena una PERSONA cuando confirma el dato en el panel.
  - Solo se crea una convocatoria si la fuente da fechas concretas.
  - El «área» de cada carrera (para el test) es una clasificación nuestra, no un dato de la universidad.

Para volver a los datos de ejemplo:  python -m backend.app.seed --reset
"""
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from sqlmodel import Session, delete

from ..app.core.config import DATABASE_URL
from ..app.core.database import engine, init_db
from ..app.models.entities import (
    Carrera, Convocatoria, Embajador, Facultad, Preuniversitario, Universidad,
)
from ..app.services.admin import _tocar

CONSULTADO = "22-nov-2026"

# ---------------------------------------------------------------------------------------------
# UMSS · fuente: buscador oficial de carreras https://www.umss.edu.bo/carreras/ (filtros por área)
# Solo licenciaturas e ingenierías; no se incluyen técnicos ni programas complementarios.
# ---------------------------------------------------------------------------------------------
UMSS_MEDICINA = "https://med.umss.edu.bo/medicina-2/"

UMSS = {
    "universidad": dict(
        nombre="Universidad Mayor de San Simón", sigla="UMSS", tipo="publica", ciudad="Cochabamba",
        departamento="Cochabamba", sitio_web="https://www.umss.edu.bo/", costo_mensual_bs=None, becas=None,
        fuente_url="https://www.umss.edu.bo/carreras/",
    ),
    "facultades": [
        ("Facultad de Ciencias Económicas", "negocios", [
            ("Administración de Empresas", "negocios", 5), ("Contaduría Pública", "negocios", 5),
            ("Economía", "negocios", 5), ("Ingeniería Comercial", "negocios", 5),
            ("Ingeniería Financiera", "negocios", 5),
        ]),
        ("Facultad de Ciencias y Tecnología", "tecnologia", [
            ("Biología", "naturaleza", 5), ("Física", "tecnologia", 5), ("Matemáticas", "tecnologia", 5),
            ("Química", "tecnologia", 5), ("Didáctica de la Física", "social", 5),
            ("Didáctica de la Matemática", "social", 5), ("Ingeniería Civil", "tecnologia", 5),
            ("Ingeniería de Alimentos", "tecnologia", 5), ("Ingeniería de Sistemas", "tecnologia", 5),
            ("Ingeniería Eléctrica", "tecnologia", 5), ("Ingeniería Electrónica", "tecnologia", 5),
            ("Ingeniería en Biotecnología", "tecnologia", 5), ("Ingeniería en Electromecánica", "tecnologia", 5),
            ("Ingeniería en Energía", "tecnologia", 5), ("Ingeniería Industrial", "tecnologia", 5),
            ("Ingeniería Informática", "tecnologia", 5), ("Ingeniería Matemática", "tecnologia", 5),
            ("Ingeniería Mecánica", "tecnologia", 5), ("Ingeniería Química", "tecnologia", 5),
        ]),
        ('Facultad de Medicina "Dr. Aurelio Meleán"', "salud", [
            ("Medicina", "salud", 6, "Ingreso por Curso Básico: convocatoria pública en la segunda quincena de octubre "
             "de cada año e inicio en diciembre. Matrícula gestión 2025-2026: Bs 1.500 (postulante por primera vez). "
             "Fuente: " + UMSS_MEDICINA),
            ("Fisioterapia y Kinesiología", "salud", 5), ("Nutrición y Dietética", "salud", 5),
        ]),
        ("Facultad de Odontología", "salud", [("Odontología", "salud", 5)]),
        ("Facultad de Enfermería", "salud", [("Enfermería", "salud", 5)]),
        ("Facultad de Ciencias Farmacéuticas y Bioquímicas", "salud", [("Bioquímica y Farmacia", "salud", 5)]),
        ("Facultad de Ciencias Jurídicas y Políticas", "social", [
            ("Ciencias Jurídicas", "social", 5), ("Ciencia Política", "social", 5),
        ]),
        ("Facultad de Ciencias Sociales", "social", [
            ("Antropología", "social", 5), ("Historia", "social", 5), ("Sociología", "social", 5),
        ]),
        ("Facultad de Humanidades y Ciencias de la Educación", "social", [
            ("Ciencias de la Educación", "social", 5), ("Comunicación Social", "arte", 5),
            ("Lingüística Aplicada a la Enseñanza de Lenguas", "social", 5), ("Música", "arte", 5),
            ("Psicología", "social", 5), ("Trabajo Social", "social", 5),
        ]),
        ("Facultad de Arquitectura y Ciencias del Hábitat", "tecnologia", [
            ("Arquitectura", "tecnologia", 5), ("Diseño de Interiores y del Mobiliario", "arte", 5),
            ("Diseño Gráfico y Comunicación Visual", "arte", 5),
            ("Planificación del Territorio y Medio Ambiente", "naturaleza", 5), ("Turismo", "negocios", 5),
        ]),
        ("Facultad de Ciencias Agrícolas, Pecuarias y Forestales", "naturaleza", [
            ("Ingeniería Agrícola", "naturaleza", 5), ("Ingeniería Agroindustrial", "naturaleza", 5),
            ("Ingeniería Agronómica", "naturaleza", 5), ("Ingeniería Agrónomo Zootecnista", "naturaleza", 5),
            ("Ingeniería Fitotecnista", "naturaleza", 5), ("Ingeniería Forestal", "naturaleza", 5),
        ]),
        ("Facultad de Ciencias Veterinarias", "naturaleza", [("Medicina Veterinaria y Zootecnia", "naturaleza", 5)]),
        ("Facultad de Desarrollo Rural y Territorial", "naturaleza", [
            ("Producción Agraria y Desarrollo Territorial", "naturaleza", 5),
            ("Ingeniería en Gestión de Recursos Hídricos Agropecuarios", "naturaleza", 4),
        ]),
        ("Facultad Politécnica del Valle Alto", "tecnologia", [
            ("Ingeniería Mecánica Automotriz y Maquinaria Agroindustrial", "tecnologia", 5),
        ]),
        ("Universidad Virtual Inteligente (programas virtuales)", "tecnologia", [
            ("Ingeniería en Inteligencia Artificial", "tecnologia", 4), ("Ingeniería en Robótica", "tecnologia", 4),
            ("Ingeniería en Gestión Empresarial con Inteligencia Artificial", "negocios", 4),
            ("Economía Conductual y Ciencia de Datos", "negocios", 4),
            ("Negocios Internacionales Digitales", "negocios", 4),
            ("Artes Audiovisuales y Cine Digital", "arte", 4), ("Periodismo Digital y Plataformas", "arte", 4),
            ("Ciencias Forenses", "social", 4), ("Criminalística", "social", 4),
            ("Relaciones Internacionales", "social", 4),
        ]),
    ],
    "convocatorias": [],  # No se encontraron fechas de admisión 2027 publicadas (22-nov-2026).
}

# ---------------------------------------------------------------------------------------------
# UCB · fuentes: https://cba.ucb.edu.bo/oferta-pregrado-ucb-cochabamba/ y
#                https://cba.ucb.edu.bo/soy-futuro-estudiante/becas-bachilleres/
# La oferta no indica duración ni costos.
# ---------------------------------------------------------------------------------------------
UCB = {
    "universidad": dict(
        nombre='Universidad Católica Boliviana "San Pablo" · Sede Cochabamba', sigla="UCB", tipo="privada",
        ciudad="Cochabamba", departamento="Cochabamba", sitio_web="https://cba.ucb.edu.bo/", costo_mensual_bs=None,
        becas="Beca Bachiller 2027: cubre el 100 % de las mensualidades durante toda la carrera. Para bachilleres "
              "bolivianos con promedio de 80/100 o más en 3ro, 4to, 5to y el 1er trimestre de 6to (o ganadores de "
              "olimpiadas). La prueba de la gestión 2026 fue el 11 de julio de 2026 (inscripción ya cerrada).",
        fuente_url="https://cba.ucb.edu.bo/oferta-pregrado-ucb-cochabamba/",
    ),
    "facultades": [
        ("Facultad de Teología San Pablo", "social", [("Teología", "social", None), ("Teología Pastoral", "social", None)]),
        ("Ciencias de la Salud", "salud", [
            ("Medicina", "salud", None), ("Enfermería", "salud", None), ("Odontología", "salud", None),
            ("Kinesiología y Fisioterapia", "salud", None),
        ]),
        ("Ingeniería y Ciencias Exactas", "tecnologia", [
            ("Arquitectura", "tecnologia", None), ("Ingeniería Ambiental", "naturaleza", None),
            ("Ingeniería Civil", "tecnologia", None), ("Ingeniería Industrial", "tecnologia", None),
            ("Ingeniería Química", "tecnologia", None), ("Ingeniería Mecatrónica", "tecnologia", None),
            ("Ingeniería de Sistemas", "tecnologia", None),
        ]),
        ("Ciencias Sociales y Humanas", "social", [
            ("Antropología", "social", None), ("Comunicación Social", "arte", None),
            ("Diseño Digital Multimedia", "arte", None), ("Derecho", "social", None),
            ("Filosofía y Letras", "social", None), ("Psicología", "social", None),
        ]),
        ("Administración y Economía", "negocios", [
            ("Administración de Empresas", "negocios", None), ("Contaduría Pública (Auditoría)", "negocios", None),
            ("Ingeniería Comercial", "negocios", None), ("Ingeniería Empresarial", "negocios", None),
            ("Ingeniería Financiera", "negocios", None),
            ("Ingeniería en Comercio y Finanzas Internacionales", "negocios", None),
        ]),
    ],
    "convocatorias": [],  # La web no publica fechas de admisión 2027 (22-nov-2026).
}

# ---------------------------------------------------------------------------------------------
# UPB · fuentes: https://www.upb.edu/programas/pregrado y https://www.upb.edu/postula-a-la-upb/nacionales
# ---------------------------------------------------------------------------------------------
UPB_POSTULA = "https://www.upb.edu/postula-a-la-upb/nacionales"
UPB = {
    "universidad": dict(
        nombre="Universidad Privada Boliviana · Campus Cochabamba", sigla="UPB", tipo="privada", ciudad="Cochabamba",
        departamento="Cochabamba", sitio_web="https://www.upb.edu/", costo_mensual_bs=None,
        becas="Beca 100 Mejores y Mérito Académico (financiamiento de hasta el 100 %), Beca Talento, Beca Patrocinio "
              "Empresarial y Beca Equidad. La página no publica montos ni requisitos: hay que consultar a admisiones.",
        fuente_url="https://www.upb.edu/programas/pregrado",
    ),
    "facultades": [
        ("Facultad de Ciencias Empresariales y Derecho", "negocios", [
            ("Administración de Empresas", "negocios", None), ("Analítica Gerencial de Datos", "negocios", None),
            ("Economía", "negocios", None), ("Ingeniería Comercial", "negocios", None),
            ("Ingeniería Financiera", "negocios", None), ("Marketing y Transformación Digital", "negocios", None),
            ("Relaciones y Negocios Internacionales", "negocios", None), ("Comunicación", "arte", None),
            ("Derecho", "social", None), ("Diseño Gráfico", "arte", None),
            ("Gerencia Global en Turismo y Hospitalidad", "negocios", None),
            ("Psicología Organizacional", "social", None),
        ]),
        ("Facultad de Ingenierías y Arquitectura", "tecnologia", [
            ("Arquitectura", "tecnologia", None), ("Ingeniería Civil", "tecnologia", None),
            ("Ingeniería del Medio Ambiente y Energías Alternativas", "naturaleza", None),
            ("Ingeniería Industrial y de Sistemas Productivos", "tecnologia", None),
            ("Bioingeniería en Recursos Naturales", "naturaleza", None),
            ("Ingeniería de Inteligencia Artificial", "tecnologia", None),
            ("Ingeniería de Sistemas Computacionales", "tecnologia", None),
            ("Ingeniería Electromecánica", "tecnologia", None), ("Ingeniería en Sistemas Electrónicos", "tecnologia", None),
        ]),
    ],
    # La tabla «Tiempos de inscripción» pone en columnas: temprana 01/01–31/07/2026, regular 01/08–31/10/2026,
    # tardía 01/11/2026–31/01/2027. Es la misma para toda la universidad.
    "convocatorias": [
        (facultad, dict(
            titulo="Admisión tardía 2027 · postulación UPB",
            inscripcion_inicio=date(2026, 11, 1), inscripcion_fin=date(2027, 1, 31), fecha_examen=None,
            modalidad_ingreso="examen", costo_inscripcion_bs=None,
            requisitos="Crear un usuario en la plataforma de postulaciones; subir ensayo, CV, libreta de 5to de "
                       "secundaria y certificado de inglés (opcional); y programar la Prueba de Aptitud Académica (PAA).",
            fuente_url=UPB_POSTULA,
        ))
        for facultad in ("Facultad de Ciencias Empresariales y Derecho", "Facultad de Ingenierías y Arquitectura")
    ],
}

# ---------------------------------------------------------------------------------------------
# Univalle · fuentes: https://www.univalle.edu/?page_id=20106 (sede Cochabamba) y ?page_id=19966
# No publica duración, costos ni fechas en texto (el calendario 2026-2027 es una imagen).
# ---------------------------------------------------------------------------------------------
UNIVALLE = {
    "universidad": dict(
        nombre="Universidad Privada del Valle · Sede Cochabamba", sigla="Univalle", tipo="privada",
        ciudad="Tiquipaya", departamento="Cochabamba", sitio_web="https://www.univalle.edu/", costo_mensual_bs=None,
        becas=None, fuente_url="https://www.univalle.edu/?page_id=20106",
    ),
    "facultades": [
        ("Facultad de Ciencias de la Salud", "salud", [
            ("Medicina", "salud", None), ("Odontología", "salud", None), ("Bioquímica y Farmacia", "salud", None),
            ("Fisioterapia y Kinesiología", "salud", None), ("Enfermería Clínico-Quirúrgica", "salud", None),
            ("Nutrición y Dietética", "salud", None),
        ]),
        ("Facultad de Ciencias Empresariales y Sociales", "negocios", [
            ("Ingeniería Comercial", "negocios", None), ("Ingeniería en Comercio Internacional", "negocios", None),
            ("Derecho y Ciencias Jurídicas", "social", None), ("Comunicación Estratégica y Digital", "arte", None),
            ("Administración de Empresas", "negocios", None), ("Psicología", "social", None),
            ("Ingeniería Financiera y de Riesgos", "negocios", None),
            ("Ingeniería en Ciencia de Datos e Inteligencia de Negocios", "tecnologia", None),
        ]),
        ("Facultad de Informática y Electrónica", "tecnologia", [
            ("Ingeniería Biomédica", "tecnologia", None), ("Ingeniería Electrónica", "tecnologia", None),
            ("Ingeniería de Sistemas Informáticos", "tecnologia", None),
        ]),
        ("Facultad de Arquitectura, Urbanismo y Diseño", "arte", [
            ("Arquitectura y Urbanismo", "tecnologia", None), ("Diseño de Interiores", "arte", None),
            ("Diseño Gráfico y Comunicación Visual", "arte", None),
        ]),
        ("Facultad de Gastronomía", "arte", [("Ciencias Gastronómicas", "arte", None)]),
        ("Facultad de Tecnología", "tecnologia", [
            ("Ingeniería Civil", "tecnologia", None), ("Ingeniería en Tecnología Alimentaria", "tecnologia", None),
            ("Ingeniería Aeronáutica", "tecnologia", None), ("Ingeniería Electromecánica", "tecnologia", None),
            ("Ingeniería Mecánica y de Automatización Industrial", "tecnologia", None),
            ("Ingeniería Industrial", "tecnologia", None), ("Ingeniería en Energía", "tecnologia", None),
        ]),
    ],
    "convocatorias": [],
}

# ---------------------------------------------------------------------------------------------
# Preuniversitarios de Cochabamba. Sin coordenadas: no se publican y no se inventan.
# ---------------------------------------------------------------------------------------------
TODAS = "ciencias_tecnologia,medicina,economicas,juridicas,arquitectura,odontologia,humanidades,bioquimica"
PREUNIVERSITARIOS = [
    dict(nombre="Curso Preuniversitario Virtual · Facultad de Ciencias y Tecnología UMSS", tipo="universidad",
         ciudad="Cochabamba", departamento="Cochabamba", duracion_meses=2, costo_bs=None, modalidad="virtual",
         prepara_para="Todas las carreras de la Facultad de Ciencias y Tecnología de la UMSS",
         materias="Aritmética,Álgebra,Geometría,Trigonometría,Física,Química,Biología",
         facultades_tipos="ciencias_tecnologia",
         descripcion="Curso oficial de la facultad, «siete semanas efectivas de clases». Dato de una nota de prensa "
                     "de mayo de 2024: confirmar si se repite y cuánto cuesta.",
         fuente_url="https://www.opinion.com.bo/articulo/cochabamba/tecnologia-umss-lanza-cursos-preuniversitarios-virtuales/20240521000012945834.html"),
    dict(nombre="Instituto INAP", tipo="instituto", ciudad="Cochabamba", departamento="Cochabamba",
         duracion_meses=None, costo_bs=None, modalidad="presencial",
         prepara_para="Examen de ingreso a la UMSS; también institutos militares y normales",
         direccion="Calle Jordán N° 723, casi Antezana", contacto="Teléfono 4501512",
         facultades_tipos=TODAS,
         descripcion="Cursos preuniversitarios para el examen de ingreso de la UMSS. La fuente no indica materias, "
                     "duración ni costo.",
         fuente_url="https://guiacochabamba.com/instituto-inap"),
    dict(nombre="Academia Preuniversitaria Lilavati", tipo="instituto", ciudad="Cochabamba", departamento="Cochabamba",
         duracion_meses=None, costo_bs=None, modalidad="presencial",
         prepara_para="Ingreso a Medicina en la UMSS",
         direccion="Calle Sucre entre 16 de Julio y Oquendo #854, edificio Arce, primer piso, of. 7",
         facultades_tipos="medicina", facebook="https://www.facebook.com/preuniversitariolilavati/",
         descripcion="Curso de preparación para el ingreso a Medicina de la UMSS, presencial. La fuente no indica "
                     "costo ni duración.",
         fuente_url="https://preuniversitariolilavati.com/"),
    dict(nombre="PreU CEPI", tipo="instituto", ciudad="Cochabamba", departamento="Cochabamba",
         duracion_meses=None, costo_bs=None, modalidad="presencial",
         prepara_para="Examen de ingreso a la UMSS 2027",
         direccion="Entre Oquendo y 16 de Julio, a media cuadra de la UMSS", facultades_tipos=TODAS,
         descripcion="Centro especializado en el examen de ingreso de la UMSS. La fuente no indica materias, "
                     "costo ni duración.",
         fuente_url="https://preuniversitariocepi.com/"),
]

UNIVERSIDADES = [UMSS, UCB, UPB, UNIVALLE]


def _respaldar() -> Optional[Path]:
    if not DATABASE_URL.startswith("sqlite:///"):
        return None
    base = Path(DATABASE_URL.removeprefix("sqlite:///"))
    if not base.exists():
        return None
    copia = base.with_name(f"guia.respaldo-{datetime.now():%Y%m%d-%H%M%S}.db")
    shutil.copy2(base, copia)
    return copia


def cargar() -> dict:
    copia = _respaldar()
    init_db()
    cuenta = {"universidades": 0, "facultades": 0, "carreras": 0, "convocatorias": 0, "preuniversitarios": 0}
    with Session(engine) as s:
        for tabla in (Convocatoria, Carrera, Facultad, Embajador, Universidad, Preuniversitario):
            s.exec(delete(tabla))
        for bloque in UNIVERSIDADES:
            uni = Universidad(**bloque["universidad"])
            s.add(uni)
            s.flush()
            cuenta["universidades"] += 1
            por_nombre = {}
            for nombre, area, carreras in bloque["facultades"]:
                fac = Facultad(universidad_id=uni.id, nombre=nombre, area=area)
                s.add(fac)
                s.flush()
                por_nombre[nombre] = fac.id
                cuenta["facultades"] += 1
                for c in carreras:
                    nombre_c, area_c, anios = c[:3]
                    descripcion = c[3] if len(c) > 3 else ""
                    s.add(Carrera(facultad_id=fac.id, nombre=nombre_c, area=area_c, duracion_anios=anios,
                                  descripcion=descripcion))
                    cuenta["carreras"] += 1
            for facultad, datos in bloque["convocatorias"]:
                s.add(Convocatoria(facultad_id=por_nombre[facultad], **datos))
                cuenta["convocatorias"] += 1
        for p in PREUNIVERSITARIOS:
            s.add(Preuniversitario(**p))
            cuenta["preuniversitarios"] += 1
        s.commit()
        _tocar(s)  # los celulares recibirán el paquete nuevo
    return {"respaldo": str(copia) if copia else None, **cuenta}


if __name__ == "__main__":
    resultado = cargar()
    print(f"Datos reales de Cochabamba cargados (consultados el {CONSULTADO}):")
    for clave, valor in resultado.items():
        print(f"  {clave}: {valor}")
