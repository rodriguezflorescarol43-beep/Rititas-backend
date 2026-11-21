import base64
import json

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from backend.app.core.migraciones import migrar


def _verificar(client, paquete) -> None:
    """Hace lo mismo que hará el celular: comprobar la firma con la clave pública."""
    clave = client.get("/api/paquete/clave").json()["clave_publica"]
    publica = serialization.load_der_public_key(base64.b64decode(clave))
    cruda = base64.b64decode(paquete["firma"])
    der = encode_dss_signature(int.from_bytes(cruda[:32], "big"), int.from_bytes(cruda[32:], "big"))
    publica.verify(der, paquete["datos"].encode(), ec.ECDSA(hashes.SHA256()))


# ---------- migración automática ----------

def test_migracion_agrega_columnas_sin_perder_datos():
    motor = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with motor.begin() as c:  # tabla «vieja», sin las columnas nuevas
        c.execute(text(
            "CREATE TABLE preuniversitario (id INTEGER PRIMARY KEY, nombre VARCHAR NOT NULL, tipo VARCHAR NOT NULL,"
            " ciudad VARCHAR NOT NULL, departamento VARCHAR NOT NULL, duracion_meses INTEGER NOT NULL, costo_bs INTEGER,"
            " modalidad VARCHAR NOT NULL, prepara_para VARCHAR NOT NULL, contacto VARCHAR, fuente_url VARCHAR, verificado_en DATE)"
        ))
        c.execute(text(
            "INSERT INTO preuniversitario (nombre,tipo,ciudad,departamento,duracion_meses,modalidad,prepara_para)"
            " VALUES ('Mi instituto','instituto','Oruro','Oruro',4,'presencial','Todo')"
        ))
    agregadas = migrar(motor)
    assert "preuniversitario.zona" in agregadas and "preuniversitario.materias" in agregadas
    columnas = {c["name"] for c in inspect(motor).get_columns("preuniversitario")}
    assert {"zona", "whatsapp", "latitud", "facultades_tipos"} <= columnas
    with motor.connect() as c:
        fila = c.execute(text("SELECT nombre, materias, zona FROM preuniversitario")).one()
    assert tuple(fila) == ("Mi instituto", "", None)  # el dato se conserva
    assert migrar(motor) == []  # volver a correrla no hace nada


# ---------- paquete firmado ----------

def test_paquete_trae_todo_y_la_firma_es_valida(client):
    r = client.get("/api/paquete")
    assert r.status_code == 200
    paquete = r.json()
    _verificar(client, paquete)
    datos = json.loads(paquete["datos"])
    assert len(datos["universidades"]) == 4 and len(datos["preguntas"]) == 8
    assert datos["preguntas"][0]["opciones"][0]["area"]  # el celular necesita el área para calcular
    assert "estado" not in datos["convocatorias"][0]  # el estado se calcula en el celular, con la fecha de hoy


def test_si_alguien_cambia_una_cifra_la_firma_no_coincide(client):
    paquete = client.get("/api/paquete").json()
    paquete["datos"] = paquete["datos"].replace('"costo_mensual_bs":50', '"costo_mensual_bs":5', 1)
    with pytest.raises(InvalidSignature):
        _verificar(client, paquete)


def test_si_no_cambio_responde_304_sin_cuerpo(client):
    primera = client.get("/api/paquete")
    etiqueta = primera.headers["etag"]
    segunda = client.get("/api/paquete", headers={"If-None-Match": etiqueta})
    assert segunda.status_code == 304 and segunda.content == b""


def test_el_servidor_comprime_las_respuestas(client):
    r = client.get("/api/paquete", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip"


def test_la_version_sube_cuando_el_administrador_cambia_algo(client, admin):
    antes = client.get("/api/paquete").json()
    nueva = {"nombre": "Universidad Nueva", "sigla": "UN", "tipo": "publica", "ciudad": "Oruro", "departamento": "Oruro"}
    assert client.post("/api/admin/universidades", json=nueva, headers=admin).status_code == 201
    despues = client.get("/api/paquete").json()
    assert despues["version"] > antes["version"]
    assert len(json.loads(despues["datos"])["universidades"]) == 5
    assert client.get("/api/paquete", headers={"If-None-Match": '"viejo"'}).status_code == 200


# ---------- preuniversitarios (perfil ampliado) ----------

def test_detalle_de_preuniversitario(client):
    lista = client.get("/api/preuniversitarios").json()
    alfa = next(p for p in lista if p["nombre"].endswith("Alfa"))
    d = client.get(f"/api/preuniversitarios/{alfa['id']}").json()
    assert d["zona"] == "Zona Norte" and "Física" in d["materias"]
    assert d["facultades_tipos"].split(",") == ["ciencias_tecnologia", "medicina", "economicas"]
    assert client.get("/api/preuniversitarios/9999").status_code == 404


def test_meta_incluye_los_tipos_de_facultad(client):
    tipos = client.get("/api/meta").json()["facultades_tipo"]
    assert tipos["medicina"]["nombre"] == "Medicina" and len(tipos) == 8


PREU = {
    "nombre": "Instituto Nuevo", "tipo": "instituto", "ciudad": "Oruro", "departamento": "Oruro",
    "duracion_meses": 3, "modalidad": "mixta",
}


def test_admin_valida_el_perfil_del_preuniversitario(client, admin):
    ok = client.post("/api/admin/preuniversitarios", headers=admin, json={
        **PREU, "whatsapp": "59170000000", "latitud": -17.8, "longitud": -63.2,
        "facultades_tipos": "medicina, juridicas", "facebook": "https://facebook.com/ejemplo",
    })
    assert ok.status_code == 201 and ok.json()["facultades_tipos"] == "medicina,juridicas"
    for malo in ({"whatsapp": "abc"}, {"latitud": 200}, {"facultades_tipos": "magia"}, {"tiktok": "javascript:alert(1)"}):
        assert client.post("/api/admin/preuniversitarios", json={**PREU, **malo}, headers=admin).status_code == 422


# ---------- embajadores ----------

def test_solo_se_muestran_embajadores_con_consentimiento(client, admin):
    publicos = client.get("/api/embajadores").json()
    assert len(publicos) == 2 and all(e["universidad_nombre"] for e in publicos)

    uni = client.get("/api/admin/universidades", headers=admin).json()[0]["id"]
    base = {"universidad_id": uni, "nombre": "Luis", "carrera": "Derecho"}

    sin_permiso = client.post("/api/admin/embajadores", json={**base, "activo": True}, headers=admin)
    assert sin_permiso.status_code == 422 and "consentimiento" in sin_permiso.json()["detail"]
    menor = client.post("/api/admin/embajadores", headers=admin, json={
        **base, "activo": True, "consentimiento": True, "consentimiento_fecha": "2026-11-21"})
    assert menor.status_code == 422  # falta ser mayor de edad

    borrador = client.post("/api/admin/embajadores", json=base, headers=admin)  # guardado pero sin publicar
    assert borrador.status_code == 201
    assert len(client.get("/api/embajadores").json()) == 2

    ok = client.post("/api/admin/embajadores", headers=admin, json={
        **base, "activo": True, "mayor_de_edad": True, "consentimiento": True, "consentimiento_fecha": "2026-11-21"})
    assert ok.status_code == 201
    assert len(client.get("/api/embajadores").json()) == 3


def test_no_se_borra_una_universidad_con_embajadores(client, admin):
    upe = next(u for u in client.get("/api/admin/universidades", headers=admin).json() if u["sigla"] == "UPE")
    r = client.delete(f"/api/admin/universidades/{upe['id']}", headers=admin)
    assert r.status_code == 409
