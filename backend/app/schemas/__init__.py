"""Capa de contratos: lo que entra y sale por la API."""
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UniversidadOut(_Out):
    id: int
    nombre: str
    sigla: str
    tipo: str
    ciudad: str
    departamento: str
    sitio_web: Optional[str] = None
    imagen_url: Optional[str] = None
    costo_mensual_bs: Optional[int] = None
    becas: Optional[str] = None
    fuente_url: Optional[str] = None
    verificado_en: Optional[date] = None


class CarreraOut(_Out):
    id: int
    nombre: str
    area: str
    duracion_anios: int
    descripcion: str = ""


class ConvocatoriaOut(_Out):
    id: int
    facultad_id: int
    titulo: str
    inscripcion_inicio: date
    inscripcion_fin: date
    fecha_examen: Optional[date] = None
    modalidad_ingreso: str
    costo_inscripcion_bs: Optional[int] = None
    requisitos: str = ""
    fuente_url: Optional[str] = None
    verificado_en: Optional[date] = None
    estado: str = "cerrada"  # abierta | proxima | cerrada
    dias_restantes: Optional[int] = None


class FacultadResumen(BaseModel):
    id: int
    nombre: str
    area: str
    area_nombre: str
    universidad_id: int
    universidad_nombre: str
    universidad_sigla: str
    tipo: str
    ciudad: str
    departamento: str
    n_carreras: int
    estado_convocatoria: Optional[str] = None


class FacultadDetalle(FacultadResumen):
    universidad: UniversidadOut
    carreras: list[CarreraOut]
    convocatorias: list[ConvocatoriaOut]


class PreuniversitarioOut(_Out):
    id: int
    nombre: str
    tipo: str
    ciudad: str
    departamento: str
    duracion_meses: int
    costo_bs: Optional[int] = None
    modalidad: str
    prepara_para: str = ""
    contacto: Optional[str] = None
    fuente_url: Optional[str] = None
    verificado_en: Optional[date] = None
    zona: Optional[str] = None
    descripcion: Optional[str] = None
    direccion: Optional[str] = None
    referencia: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    whatsapp: Optional[str] = None
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    tiktok: Optional[str] = None
    imagen_url: Optional[str] = None
    materias: str = ""
    facultades_tipos: str = ""


class EmbajadorOut(BaseModel):
    id: int
    nombre: str
    universidad_id: int
    universidad_nombre: str
    carrera: str
    mensaje: Optional[str] = None
    whatsapp: Optional[str] = None


class OpcionOut(_Out):
    id: int
    texto: str
    icono: str


class PreguntaOut(BaseModel):
    id: int
    texto: str
    opciones: list[OpcionOut]


class OrientacionIn(BaseModel):
    opciones: list[int] = Field(min_length=1, max_length=50)
    departamento: Optional[str] = None
    presupuesto_max_bs: Optional[int] = Field(default=None, ge=0)
    puede_mudarse: bool = True


class AreaPuntaje(BaseModel):
    area: str
    nombre: str
    porcentaje: int


class Recomendacion(BaseModel):
    carrera_id: int
    carrera: str
    facultad_id: int
    facultad: str
    universidad: str
    tipo: str
    ciudad: str
    departamento: str
    area: str
    area_nombre: str
    costo_mensual_bs: Optional[int] = None
    requiere_mudarse: bool
    estado_convocatoria: Optional[str] = None
    motivo: str


class OrientacionOut(BaseModel):
    areas: list[AreaPuntaje]
    recomendaciones: list[Recomendacion]
    aviso: str


class MensajeIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=120)
    mensaje: str = Field(min_length=5, max_length=1000)


class MensajeOut(_Out):
    id: int
    nombre: str
