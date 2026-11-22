"""Capa de dominio: tablas de la base de datos.

Cada dato oficial lleva `fuente_url` y `verificado_en`. Si `verificado_en` es
nulo, la interfaz lo muestra como "dato de ejemplo, sin verificar".
"""
from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

AREAS = {
    "salud": "Salud",
    "tecnologia": "Tecnología e ingeniería",
    "negocios": "Negocios y administración",
    "social": "Sociedad, derecho y educación",
    "arte": "Arte y comunicación",
    "naturaleza": "Naturaleza y agro",
}


# Tipos generales de facultad para buscar preuniversitarios (no son las facultades de cada universidad).
FACULTADES_TIPO = {
    # `orden` fija cómo se muestran (el paquete firmado ordena las claves alfabéticamente).
    "ciencias_tecnologia": {"nombre": "Ciencias y Tecnología", "icono": "ti-cpu", "orden": 1},
    "medicina": {"nombre": "Medicina", "icono": "ti-stethoscope", "orden": 2},
    "economicas": {"nombre": "Ciencias Económicas", "icono": "ti-chart-line", "orden": 3},
    "juridicas": {"nombre": "Ciencias Jurídicas", "icono": "ti-scale", "orden": 4},
    "arquitectura": {"nombre": "Arquitectura", "icono": "ti-building-skyscraper", "orden": 5},
    "odontologia": {"nombre": "Odontología", "icono": "ti-dental", "orden": 6},
    "humanidades": {"nombre": "Humanidades", "icono": "ti-book", "orden": 7},
    "bioquimica": {"nombre": "Bioquímica y Farmacia", "icono": "ti-flask", "orden": 8},
}


class Universidad(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str
    sigla: str
    tipo: str  # publica | privada | tecnico
    ciudad: str
    departamento: str
    sitio_web: Optional[str] = None
    imagen_url: Optional[str] = None
    costo_mensual_bs: Optional[int] = None
    becas: Optional[str] = None
    fuente_url: Optional[str] = None
    verificado_en: Optional[date] = None


class Facultad(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    universidad_id: int = Field(foreign_key="universidad.id", index=True)
    nombre: str
    area: str


class Carrera(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    facultad_id: int = Field(foreign_key="facultad.id", index=True)
    nombre: str
    area: str
    duracion_anios: Optional[int] = None  # vacío = la universidad no la publica
    descripcion: str = ""


class Convocatoria(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    facultad_id: int = Field(foreign_key="facultad.id", index=True)
    titulo: str
    inscripcion_inicio: date
    inscripcion_fin: date
    fecha_examen: Optional[date] = None
    modalidad_ingreso: str  # examen | preuniversitario | ambos
    costo_inscripcion_bs: Optional[int] = None
    requisitos: str = ""
    fuente_url: Optional[str] = None
    verificado_en: Optional[date] = None


class Preuniversitario(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str
    tipo: str  # instituto | universidad
    ciudad: str
    departamento: str
    duracion_meses: Optional[int] = None  # vacío = el instituto no la publica
    costo_bs: Optional[int] = None
    modalidad: str  # presencial | virtual | mixta
    prepara_para: str = ""
    contacto: Optional[str] = None
    fuente_url: Optional[str] = None
    verificado_en: Optional[date] = None
    # Perfil ampliado (agregado después: la migración automática lo suma a bases existentes).
    zona: Optional[str] = None
    descripcion: Optional[str] = None
    direccion: Optional[str] = None
    referencia: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    whatsapp: Optional[str] = None  # solo dígitos con código de país, por ejemplo 59170000000
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    tiktok: Optional[str] = None
    imagen_url: Optional[str] = None
    materias: str = ""  # separadas por coma
    facultades_tipos: str = ""  # claves de FACULTADES_TIPO separadas por coma


class Embajador(SQLModel, table=True):
    """Estudiante voluntario que, con su consentimiento, orienta a quien quiere entrar a su universidad."""

    id: Optional[int] = Field(default=None, primary_key=True)
    universidad_id: int = Field(foreign_key="universidad.id", index=True)
    nombre: str
    carrera: str
    mensaje: Optional[str] = None
    whatsapp: Optional[str] = None
    mayor_de_edad: bool = False
    consentimiento: bool = False
    consentimiento_fecha: Optional[date] = None
    activo: bool = False


class RegistroCambio(SQLModel, table=True):
    """Historial de lo que se aprobó desde una propuesta: qué cambió, de qué fuente y con qué cita."""

    id: Optional[int] = Field(default=None, primary_key=True)
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    recurso: str
    fila_id: Optional[int] = None
    accion: str  # crear | actualizar
    fuente: Optional[str] = None
    origen: Optional[str] = None
    antes: Optional[str] = None  # JSON
    despues: Optional[str] = None  # JSON
    evidencia: Optional[str] = None  # JSON: campo -> cita textual de la fuente


class Pregunta(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    texto: str
    orden: int


class Opcion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pregunta_id: int = Field(foreign_key="pregunta.id", index=True)
    texto: str
    area: str
    icono: str = "ti-circle"


class Ajuste(SQLModel, table=True):
    """Textos y medios editables de la portada (clave → valor)."""

    clave: str = Field(primary_key=True)
    valor: str = ""


class Media(SQLModel, table=True):
    """Imagen o video subido por el administrador."""

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str
    archivo: str = Field(unique=True)
    tipo: str  # imagen | video
    mime: str
    tamano_bytes: int
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Mensaje(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str
    email: str
    mensaje: str
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
