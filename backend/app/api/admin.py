"""Capa de API del panel de administración (todo bajo /api/admin).

`/login` es público; el resto exige un token válido. Los archivos subidos se
entregan después desde /media.
"""
from contextlib import contextmanager

from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, UploadFile
from sqlmodel import Session

from ..core.config import LIMITE_VIDEO
from ..core.database import get_session
from ..core.security import (
    contrasena_correcta,
    crear_token,
    limite_login,
    requerir_admin,
)
from ..repositories import admin as repo
from ..schemas.admin import LoginIn, MediaOut
from ..services import admin as servicio
from ..services import medicion as servicio_medicion
from ..services import medios
from ..services import propuestas as servicio_propuestas
from ..services import revision as servicio_revision
from ..services.errores import (
    ArchivoInvalido,
    Conflicto,
    Invalido,
    NoEncontrado,
    RecursoDesconocido,
)

router_login = APIRouter()
router = APIRouter(dependencies=[Depends(requerir_admin)])


@contextmanager
def _errores():
    try:
        yield
    except (RecursoDesconocido, NoEncontrado) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Invalido as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Conflicto as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ArchivoInvalido as e:
        raise HTTPException(status_code=e.estado, detail=str(e))


@router_login.post("/login")
def login(datos: LoginIn, request: Request):
    clave = request.client.host if request.client else "desconocido"
    if limite_login.bloqueado(clave):
        raise HTTPException(status_code=429, detail="Demasiados intentos. Espera un minuto.")
    if not contrasena_correcta(datos.password):
        limite_login.registrar_fallo(clave)
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    limite_login.limpiar(clave)
    token, expira = crear_token()
    return {"token": token, "expira_en": expira}


@router.get("/resumen")
def resumen(session: Session = Depends(get_session)):
    return servicio.resumen(session)


@router.get("/mensajes")
def mensajes(session: Session = Depends(get_session)):
    return servicio.mensajes(session)


@router.delete("/mensajes/{mensaje_id}", status_code=204)
def borrar_mensaje(mensaje_id: int, session: Session = Depends(get_session)):
    with _errores():
        servicio.borrar_mensaje(session, mensaje_id)


@router.get("/media", response_model=list[MediaOut])
def listar_medios(session: Session = Depends(get_session)):
    return [medios.a_salida(m) for m in repo.medios(session)]


@router.post("/media", response_model=MediaOut, status_code=201)
def subir_medio(archivo: UploadFile = File(...), session: Session = Depends(get_session)):
    # Se lee un byte más que el máximo para poder rechazar archivos demasiado grandes.
    contenido = archivo.file.read(LIMITE_VIDEO + 1)
    with _errores():
        return medios.a_salida(medios.guardar(session, archivo.filename or "archivo", contenido))


@router.delete("/media/{media_id}", status_code=204)
def borrar_medio(media_id: int, session: Session = Depends(get_session)):
    with _errores():
        medios.borrar(session, media_id)


@router.get("/revision")
def revision(session: Session = Depends(get_session)):
    """El Detective: qué conviene revisar hoy (reglas y estadística, sin IA externa)."""
    return servicio_revision.revisar(session)


@router.get("/referencias")
def referencias(session: Session = Depends(get_session)):
    return servicio_propuestas.referencias(session)


@router.get("/registro")
def registro(session: Session = Depends(get_session)):
    return servicio_propuestas.registro(session)


@router.post("/propuestas/analizar")
def analizar_propuesta(propuesta: dict = Body(...), session: Session = Depends(get_session)):
    """Revisa una propuesta SIN guardar nada: muestra el antes y el después."""
    with _errores():
        return servicio_propuestas.analizar(session, propuesta)


@router.post("/propuestas/aplicar")
def aplicar_propuesta(cuerpo: dict = Body(...), session: Session = Depends(get_session)):
    """Aplica solo los cambios que la persona aprobó."""
    with _errores():
        return servicio_propuestas.aplicar(session, cuerpo.get("propuesta"), cuerpo.get("aprobados"))


@router.post("/mediciones")
def medir_ia(cuerpo: dict = Body(...), session: Session = Depends(get_session)):
    """Compara la propuesta de una IA con la verdad, la pone al lado de un método sin IA y lo guarda."""
    with _errores():
        return servicio_medicion.medir(session, cuerpo)


@router.get("/mediciones")
def mediciones(session: Session = Depends(get_session)):
    return servicio_medicion.listar(session)


@router.put("/ajustes")
def guardar_ajustes(datos: dict = Body(...), session: Session = Depends(get_session)):
    with _errores():
        return servicio.guardar_ajustes(session, datos)


@router.get("/{recurso}")
def listar(recurso: str, session: Session = Depends(get_session)):
    with _errores():
        return servicio.listar(session, recurso)


@router.post("/{recurso}", status_code=201)
def crear(recurso: str, cuerpo: dict = Body(...), session: Session = Depends(get_session)):
    with _errores():
        return servicio.crear(session, recurso, cuerpo)


@router.put("/{recurso}/{fila_id}")
def actualizar(recurso: str, fila_id: int, cuerpo: dict = Body(...), session: Session = Depends(get_session)):
    with _errores():
        return servicio.actualizar(session, recurso, fila_id, cuerpo)


@router.delete("/{recurso}/{fila_id}", status_code=204)
def borrar(recurso: str, fila_id: int, session: Session = Depends(get_session)):
    with _errores():
        servicio.borrar(session, recurso, fila_id)
