"""Contratos del panel de administración: validan todo lo que se guarda."""
from datetime import date, datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from ..models.entities import FACULTADES_TIPO

Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Url = Optional[Annotated[str, StringConstraints(pattern=r"^https?://\S+$", max_length=300)]]
UrlMedia = Optional[Annotated[str, StringConstraints(pattern=r"^/media/[A-Za-z0-9_.-]+$", max_length=200)]]
Whatsapp = Optional[Annotated[str, StringConstraints(pattern=r"^\d{8,15}$")]]  # solo dígitos, con código de país
Area = Literal["salud", "tecnologia", "negocios", "social", "arte", "naturaleza"]


class UniversidadIn(BaseModel):
    nombre: Texto
    sigla: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
    tipo: Literal["publica", "privada", "tecnico"]
    ciudad: Texto
    departamento: Texto
    sitio_web: Url = None
    imagen_url: UrlMedia = None
    costo_mensual_bs: Optional[int] = Field(default=None, ge=0, le=100000)
    becas: Optional[str] = Field(default=None, max_length=300)
    fuente_url: Url = None
    verificado_en: Optional[date] = None
    descripcion: Optional[str] = Field(default=None, max_length=300)
    contacto: Optional[str] = Field(default=None, max_length=120)
    facebook: Url = None
    instagram: Url = None
    tiktok: Url = None


class FacultadIn(BaseModel):
    universidad_id: int
    nombre: Texto
    area: Area
    convocatoria_imagen_url: UrlMedia = None


class CarreraIn(BaseModel):
    facultad_id: int
    nombre: Texto
    area: Area
    duracion_anios: Optional[int] = Field(default=None, ge=1, le=10)
    descripcion: str = Field(default="", max_length=500)


class ConvocatoriaIn(BaseModel):
    facultad_id: int
    titulo: Texto
    inscripcion_inicio: date
    inscripcion_fin: date
    fecha_examen: Optional[date] = None
    modalidad_ingreso: Literal["examen", "preuniversitario", "ambos"]
    costo_inscripcion_bs: Optional[int] = Field(default=None, ge=0, le=100000)
    requisitos: str = Field(default="", max_length=800)
    fuente_url: Url = None
    verificado_en: Optional[date] = None

    @model_validator(mode="after")
    def _fechas_coherentes(self):
        if self.inscripcion_fin < self.inscripcion_inicio:
            raise ValueError("La inscripción no puede terminar antes de empezar")
        return self


class PreuniversitarioIn(BaseModel):
    nombre: Texto
    tipo: Literal["instituto", "universidad"]
    ciudad: Texto
    departamento: Texto
    duracion_meses: Optional[int] = Field(default=None, ge=1, le=24)
    costo_bs: Optional[int] = Field(default=None, ge=0, le=100000)
    modalidad: Literal["presencial", "virtual", "mixta"]
    prepara_para: str = Field(default="", max_length=200)
    contacto: Optional[str] = Field(default=None, max_length=120)
    fuente_url: Url = None
    verificado_en: Optional[date] = None
    zona: Optional[str] = Field(default=None, max_length=80)
    descripcion: Optional[str] = Field(default=None, max_length=400)
    direccion: Optional[str] = Field(default=None, max_length=160)
    referencia: Optional[str] = Field(default=None, max_length=160)
    latitud: Optional[float] = Field(default=None, ge=-90, le=90)
    longitud: Optional[float] = Field(default=None, ge=-180, le=180)
    whatsapp: Whatsapp = None
    facebook: Url = None
    instagram: Url = None
    tiktok: Url = None
    imagen_url: UrlMedia = None
    materias: str = Field(default="", max_length=300)
    facultades_tipos: str = Field(default="", max_length=200)

    @field_validator("facultades_tipos")
    @classmethod
    def _tipos_validos(cls, valor: str) -> str:
        claves = [c.strip() for c in valor.split(",") if c.strip()]
        invalidas = [c for c in claves if c not in FACULTADES_TIPO]
        if invalidas:
            raise ValueError(f"Facultades desconocidas: {', '.join(invalidas)}")
        return ",".join(claves)


class EmbajadorIn(BaseModel):
    universidad_id: int
    nombre: Texto
    carrera: Texto
    mensaje: Optional[str] = Field(default=None, max_length=300)
    whatsapp: Whatsapp = None
    mayor_de_edad: bool = False
    consentimiento: bool = False
    consentimiento_fecha: Optional[date] = None
    activo: bool = False

    @model_validator(mode="after")
    def _solo_publicar_con_consentimiento(self):
        if self.activo and not (self.mayor_de_edad and self.consentimiento and self.consentimiento_fecha):
            raise ValueError(
                "Para publicar a un embajador debe ser mayor de 18 años, haber dado su consentimiento "
                "y debe constar la fecha del consentimiento"
            )
        return self


class LoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class MediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    archivo: str
    url: str
    tipo: str
    mime: str
    tamano_bytes: int
    creado_en: datetime
