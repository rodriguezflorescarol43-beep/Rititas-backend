"""Datos de EJEMPLO para probar la página.

Las instituciones de aquí son inventadas y no tienen `verificado_en`: la interfaz
las muestra como «dato de ejemplo, sin verificar». Para publicar datos reales,
reemplaza estos registros por los oficiales y llena `fuente_url` y `verificado_en`.

Uso:  python -m backend.app.seed [--reset]
"""
import sys
from datetime import date, timedelta

from sqlmodel import Session, SQLModel, select

from .core.database import engine, init_db
from .models.entities import (
    Carrera,
    Convocatoria,
    Embajador,
    Facultad,
    Opcion,
    Preuniversitario,
    Pregunta,
    Universidad,
)

# (nombre, sigla, tipo, ciudad, departamento, costo_mensual_bs, becas)
UNIVERSIDADES = [
    ("Universidad Pública Ejemplo", "UPE", "publica", "Cochabamba", "Cochabamba", 50, "Becas de comedor y de transporte (ejemplo)"),
    ("Universidad Privada Ejemplo", "UPRE", "privada", "Santa Cruz de la Sierra", "Santa Cruz", 1500, "Descuento por rendimiento (ejemplo)"),
    ("Universidad Pública Ejemplo del Norte", "UPEN", "publica", "La Paz", "La Paz", 40, "Beca de residencia para estudiantes de provincia (ejemplo)"),
    ("Instituto Técnico Ejemplo", "ITE", "tecnico", "Cochabamba", "Cochabamba", 400, None),
]

# universidad (sigla) -> [(facultad, area, [(carrera, años, descripción)])]
FACULTADES = {
    "UPE": [
        ("Facultad de Medicina y Salud", "salud", [("Medicina", 6, "Diagnóstico y cuidado de la salud de las personas."), ("Enfermería", 4, "Cuidado directo de pacientes y apoyo en centros de salud.")]),
        ("Facultad de Ingeniería", "tecnologia", [("Ingeniería de Sistemas", 5, "Software, redes y datos."), ("Ingeniería Civil", 5, "Caminos, puentes, agua y edificios.")]),
        ("Facultad de Ciencias Económicas", "negocios", [("Administración de Empresas", 4, "Dirigir y organizar negocios."), ("Contaduría Pública", 4, "Cuentas, impuestos y control financiero.")]),
        ("Facultad de Derecho", "social", [("Derecho", 5, "Leyes, justicia y defensa de derechos.")]),
    ],
    "UPRE": [
        ("Facultad de Tecnología", "tecnologia", [("Ingeniería de Sistemas", 5, "Software, redes y datos."), ("Ingeniería Electrónica", 5, "Circuitos, sensores y automatización.")]),
        ("Facultad de Negocios", "negocios", [("Marketing y Publicidad", 4, "Cómo llegar a los clientes."), ("Administración de Empresas", 4, "Dirigir y organizar negocios.")]),
        ("Facultad de Comunicación y Arte", "arte", [("Comunicación Social", 4, "Prensa, radio, video y redes."), ("Diseño Gráfico", 4, "Imagen, marcas y piezas visuales.")]),
    ],
    "UPEN": [
        ("Facultad de Agronomía", "naturaleza", [("Ingeniería Agronómica", 5, "Producción de cultivos y suelos."), ("Ingeniería Ambiental", 5, "Agua, residuos y cuidado del entorno.")]),
        ("Facultad de Humanidades y Educación", "social", [("Ciencias de la Educación", 4, "Enseñanza y gestión educativa."), ("Trabajo Social", 4, "Apoyo a familias y comunidades.")]),
        ("Facultad de Salud", "salud", [("Enfermería", 4, "Cuidado directo de pacientes y apoyo en centros de salud.")]),
    ],
    "ITE": [
        ("Área Técnica · Informática", "tecnologia", [("Técnico Superior en Sistemas Informáticos", 3, "Soporte, redes y programación básica.")]),
        ("Área Técnica · Agropecuaria", "naturaleza", [("Técnico Superior en Producción Agropecuaria", 3, "Cultivos y ganadería en el campo.")]),
    ],
}

# (sigla, facultad, días hasta inicio, días hasta fin, días hasta examen)
CONVOCATORIAS = [
    ("UPE", "Facultad de Ingeniería", -10, 12, 25),
    ("UPE", "Facultad de Medicina y Salud", 20, 45, 60),
    ("UPE", "Facultad de Ciencias Económicas", -60, -30, -20),
    ("UPE", "Facultad de Derecho", -5, 20, 35),
    ("UPRE", "Facultad de Tecnología", -3, 40, None),
    ("UPRE", "Facultad de Negocios", -3, 40, None),
    ("UPRE", "Facultad de Comunicación y Arte", 15, 50, None),
    ("UPEN", "Facultad de Agronomía", -8, 14, 30),
    ("UPEN", "Facultad de Humanidades y Educación", 25, 55, 70),
    ("UPEN", "Facultad de Salud", -70, -40, -30),
    ("ITE", "Área Técnica · Informática", -2, 60, None),
    ("ITE", "Área Técnica · Agropecuaria", 10, 70, None),
]

# (nombre, tipo, ciudad, departamento, meses, costo, modalidad, prepara_para)
PREUNIVERSITARIOS = [
    ("Instituto Preuniversitario Ejemplo Alfa", "instituto", "Cochabamba", "Cochabamba", 4, 600, "presencial", "Ingeniería, Salud y Economía"),
    ("Instituto Preuniversitario Ejemplo Beta", "instituto", "La Paz", "La Paz", 3, 450, "mixta", "Todas las facultades"),
    ("Preuniversitario Virtual Ejemplo Gamma", "instituto", "Santa Cruz de la Sierra", "Santa Cruz", 5, 350, "virtual", "Ingreso por examen"),
    ("Preuniversitario de la Universidad Pública Ejemplo", "universidad", "Cochabamba", "Cochabamba", 6, 300, "presencial", "Ingreso a la UPE"),
    ("Instituto Preuniversitario Ejemplo Delta", "instituto", "Potosí", "Potosí", 4, 380, "presencial", "Ingeniería y Educación"),
]

# Cada pregunta: (texto, [(opción, área, icono)])
PREGUNTAS = [
    ("¿Qué disfrutas hacer en tu tiempo libre?", [
        ("Ayudar o cuidar a otras personas", "salud", "ti-heart-handshake"),
        ("Armar, programar o arreglar cosas", "tecnologia", "ti-tool"),
        ("Dibujar, filmar o crear", "arte", "ti-palette"),
        ("Estar con plantas y animales", "naturaleza", "ti-plant")]),
    ("¿Qué materia te gusta más en el colegio?", [
        ("Biología y química", "salud", "ti-flask"),
        ("Matemática y física", "tecnologia", "ti-calculator"),
        ("Historia, lenguaje o filosofía", "social", "ti-book"),
        ("Economía o contabilidad", "negocios", "ti-coin")]),
    ("Si tuvieras que hacer un proyecto, ¿cuál elegirías?", [
        ("Una campaña de salud en tu comunidad", "salud", "ti-first-aid-kit"),
        ("Crear una aplicación o un aparato", "tecnologia", "ti-device-laptop"),
        ("Abrir un negocio", "negocios", "ti-building-store"),
        ("Mejorar un cultivo", "naturaleza", "ti-seeding")]),
    ("¿Cómo te gustaría trabajar?", [
        ("Con personas, escuchando y orientando", "social", "ti-users"),
        ("Con números y planes", "negocios", "ti-chart-bar"),
        ("Con ideas visuales o historias", "arte", "ti-camera"),
        ("Con máquinas y computadoras", "tecnologia", "ti-cpu")]),
    ("¿Qué problema de tu comunidad te gustaría resolver?", [
        ("Falta de atención médica", "salud", "ti-stethoscope"),
        ("Falta de justicia o de educación", "social", "ti-scale"),
        ("Falta de internet o de caminos", "tecnologia", "ti-antenna"),
        ("Cuidado del agua y de la tierra", "naturaleza", "ti-droplet")]),
    ("¿Qué palabra te describe mejor?", [
        ("Paciente y atento", "salud", "ti-heart"),
        ("Curioso y ordenado", "tecnologia", "ti-bulb"),
        ("Líder y negociador", "negocios", "ti-speakerphone"),
        ("Creativo y expresivo", "arte", "ti-brush")]),
    ("Elige una tarea para un día", [
        ("Explicar algo a otras personas", "social", "ti-school"),
        ("Diseñar un afiche o un video", "arte", "ti-movie"),
        ("Calcular costos y ganancias", "negocios", "ti-calculator"),
        ("Cuidar a una persona enferma", "salud", "ti-bed")]),
    ("¿Dónde te imaginas dentro de 10 años?", [
        ("En un hospital o centro de salud", "salud", "ti-building-hospital"),
        ("En una empresa de tecnología", "tecnologia", "ti-device-desktop"),
        ("En el campo o en un proyecto ambiental", "naturaleza", "ti-tree"),
        ("En un colegio, un juzgado o una radio", "social", "ti-microphone")]),
]


# Perfil ampliado de los preuniversitarios de ejemplo (clave: nombre). Datos inventados.
PERFILES = {
    "Instituto Preuniversitario Ejemplo Alfa": dict(
        zona="Zona Norte", direccion="Av. Ejemplo 123", referencia="Frente a la plaza principal",
        latitud=-17.3735, longitud=-66.1568, materias="Matemáticas,Física,Química,Razonamiento",
        facultades_tipos="ciencias_tecnologia,medicina,economicas",
        descripcion="Preparación para el examen de ingreso a la universidad."),
    "Instituto Preuniversitario Ejemplo Beta": dict(
        zona="Zona Central", direccion="Calle Ejemplo 45", referencia="A media cuadra del mercado",
        latitud=-16.4955, longitud=-68.1336, materias="Matemáticas,Lenguaje,Razonamiento",
        facultades_tipos="humanidades,juridicas",
        descripcion="Clases presenciales y por internet para quien vive lejos."),
    "Preuniversitario Virtual Ejemplo Gamma": dict(
        zona="Virtual", materias="Matemáticas,Razonamiento", facultades_tipos="ciencias_tecnologia",
        descripcion="Todo el curso por internet, con clases grabadas para verlas cuando haya señal."),
    "Preuniversitario de la Universidad Pública Ejemplo": dict(
        zona="Zona Sur", direccion="Campus de la UPE", referencia="Puerta principal",
        latitud=-17.4000, longitud=-66.1500, materias="Matemáticas,Física,Química,Biología",
        facultades_tipos="ciencias_tecnologia,medicina,juridicas,odontologia,bioquimica",
        descripcion="Curso oficial de preparación para el ingreso a la UPE."),
    "Instituto Preuniversitario Ejemplo Delta": dict(
        zona="Centro", direccion="Plaza Ejemplo s/n", referencia="Cerca de la terminal",
        latitud=-19.5836, longitud=-65.7531, materias="Matemáticas,Lenguaje,Dibujo",
        facultades_tipos="ciencias_tecnologia,humanidades,arquitectura",
        descripcion="Instituto con horarios de tarde para quien trabaja."),
}


def completar_ejemplos(session: Session, hoy: date | None = None) -> None:
    """Llena el perfil ampliado y los embajadores de ejemplo SIN tocar lo que ya cargaste a mano."""
    hoy = hoy or date.today()
    for nombre, datos in PERFILES.items():
        fila = session.exec(select(Preuniversitario).where(Preuniversitario.nombre == nombre)).first()
        if fila is not None and fila.zona is None:
            for clave, valor in datos.items():
                setattr(fila, clave, valor)
            session.add(fila)
    if session.exec(select(Embajador)).first() is None:
        for sigla, nombre, carrera, mensaje in [
            ("UPE", "Estudiante de ejemplo 1", "Ingeniería de Sistemas", "Te cuento cómo es el examen y cómo me preparé. (ejemplo)"),
            ("UPEN", "Estudiante de ejemplo 2", "Enfermería", "Vine de provincia: te explico cómo conseguí la beca de residencia. (ejemplo)"),
        ]:
            uni = session.exec(select(Universidad).where(Universidad.sigla == sigla)).first()
            if uni is not None:
                session.add(Embajador(universidad_id=uni.id, nombre=nombre, carrera=carrera, mensaje=mensaje,
                                      mayor_de_edad=True, consentimiento=True, consentimiento_fecha=hoy, activo=True))
    session.commit()


def sembrar(session: Session, hoy: date | None = None) -> None:
    hoy = hoy or date.today()
    if session.exec(select(Universidad)).first():
        completar_ejemplos(session, hoy)
        return

    unis: dict[str, Universidad] = {}
    for nombre, sigla, tipo, ciudad, depto, costo, becas in UNIVERSIDADES:
        u = Universidad(nombre=nombre, sigla=sigla, tipo=tipo, ciudad=ciudad,
                        departamento=depto, costo_mensual_bs=costo, becas=becas)
        session.add(u)
        unis[sigla] = u
    session.commit()

    facs: dict[tuple[str, str], Facultad] = {}
    for sigla, lista in FACULTADES.items():
        for nombre_f, area, carreras in lista:
            f = Facultad(universidad_id=unis[sigla].id, nombre=nombre_f, area=area)
            session.add(f)
            session.commit()
            session.refresh(f)
            facs[(sigla, nombre_f)] = f
            for nombre_c, anios, desc in carreras:
                session.add(Carrera(facultad_id=f.id, nombre=nombre_c, area=area,
                                    duracion_anios=anios, descripcion=desc))

    for sigla, nombre_f, ini, fin, exa in CONVOCATORIAS:
        f = facs[(sigla, nombre_f)]
        session.add(Convocatoria(
            facultad_id=f.id,
            titulo=f"Convocatoria de ingreso · {nombre_f}",
            inscripcion_inicio=hoy + timedelta(days=ini),
            inscripcion_fin=hoy + timedelta(days=fin),
            fecha_examen=hoy + timedelta(days=exa) if exa is not None else None,
            modalidad_ingreso="ambos" if exa is not None else "preuniversitario",
            costo_inscripcion_bs=120,
            requisitos="Título de bachiller, cédula de identidad y fotografías (ejemplo).",
        ))

    for nombre, tipo, ciudad, depto, meses, costo, modalidad, prepara in PREUNIVERSITARIOS:
        session.add(Preuniversitario(nombre=nombre, tipo=tipo, ciudad=ciudad, departamento=depto,
                                     duracion_meses=meses, costo_bs=costo, modalidad=modalidad,
                                     prepara_para=prepara))

    for orden, (texto, opciones) in enumerate(PREGUNTAS, start=1):
        p = Pregunta(texto=texto, orden=orden)
        session.add(p)
        session.commit()
        session.refresh(p)
        for texto_o, area, icono in opciones:
            session.add(Opcion(pregunta_id=p.id, texto=texto_o, area=area, icono=icono))

    session.commit()
    completar_ejemplos(session, hoy)


if __name__ == "__main__":
    if "--reset" in sys.argv:
        SQLModel.metadata.drop_all(engine)
    init_db()
    with Session(engine) as s:
        sembrar(s)
    print("Datos de ejemplo cargados.")
