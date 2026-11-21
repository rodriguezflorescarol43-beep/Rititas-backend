"""Capa de API: universidades, facultades, convocatorias, institutos y metadatos."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ..core import firma
from ..core.database import get_session
from ..models.entities import AREAS, FACULTADES_TIPO
from ..repositories import catalogo as repo
from ..schemas import (
    ConvocatoriaOut,
    EmbajadorOut,
    FacultadDetalle,
    FacultadResumen,
    PreuniversitarioOut,
    UniversidadOut,
)
from ..services import admin as admin_servicio
from ..services import catalogo as servicio
from ..services import paquete as servicio_paquete

router = APIRouter()


@router.get("/meta")
def meta(session: Session = Depends(get_session)):
    return {"departamentos": repo.departamentos(session), "areas": AREAS, "facultades_tipo": FACULTADES_TIPO}


@router.get("/paquete")
def paquete(request: Request, session: Session = Depends(get_session)):
    """Todo el catálogo en una sola respuesta firmada. Si no cambió, responde 304 sin cuerpo."""
    preparado = servicio_paquete.preparar(session)
    etiqueta = servicio_paquete.etiqueta(preparado)
    cabeceras = {"ETag": etiqueta, "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == etiqueta:
        return Response(status_code=304, headers=cabeceras)
    return JSONResponse(servicio_paquete.con_firma(preparado), headers=cabeceras)


@router.get("/paquete/clave")
def clave_del_paquete():
    return {"algoritmo": "ECDSA-P256-SHA256", "clave_publica": firma.clave_publica()}


@router.get("/embajadores", response_model=list[EmbajadorOut])
def embajadores(session: Session = Depends(get_session)):
    return servicio.listar_embajadores(session)


@router.get("/ajustes")
def ajustes(session: Session = Depends(get_session)):
    """Textos y medios de la portada, editables desde el panel de administración."""
    return admin_servicio.leer_ajustes(session)


@router.get("/universidades", response_model=list[UniversidadOut])
def universidades(
    tipo: Optional[str] = Query(None, pattern="^(publica|privada|tecnico)$"),
    departamento: Optional[str] = None,
    session: Session = Depends(get_session),
):
    return repo.listar_universidades(session, tipo, departamento)


@router.get("/facultades", response_model=list[FacultadResumen])
def facultades(
    universidad_id: Optional[int] = None,
    area: Optional[str] = None,
    session: Session = Depends(get_session),
):
    return servicio.listar_facultades(session, universidad_id, area)


@router.get("/facultades/{facultad_id}", response_model=FacultadDetalle)
def facultad(facultad_id: int, session: Session = Depends(get_session)):
    try:
        return servicio.detalle_facultad(session, facultad_id)
    except servicio.NoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/convocatorias", response_model=list[ConvocatoriaOut])
def convocatorias(
    estado: Optional[str] = Query(None, pattern="^(abierta|proxima|cerrada)$"),
    session: Session = Depends(get_session),
):
    return servicio.listar_convocatorias(session, estado)


@router.get("/preuniversitarios", response_model=list[PreuniversitarioOut])
def preuniversitarios(
    departamento: Optional[str] = None, session: Session = Depends(get_session)
):
    return repo.listar_preuniversitarios(session, departamento)


@router.get("/preuniversitarios/{preu_id}", response_model=PreuniversitarioOut)
def preuniversitario(preu_id: int, session: Session = Depends(get_session)):
    fila = repo.obtener_preuniversitario(session, preu_id)
    if fila is None:
        raise HTTPException(status_code=404, detail="Preuniversitario no encontrado")
    return fila
