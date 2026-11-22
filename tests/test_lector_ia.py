"""«Leer con IA» (Gemini): se prueba sin internet simulando la respuesta del modelo."""
import json

import pytest

from backend.app.core import config
from backend.app.services import lector_ia
from backend.app.services.errores import ServicioNoDisponible

PDF = b"%PDF-1.4 contenido de prueba"


def _respuesta(propuesta):
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(propuesta)}]}}]}


def _propuesta(facultad):
    return {"formato": 1, "cambios": [{
        "accion": "crear", "recurso": "convocatorias",
        "referencias": {"universidad": facultad["universidad"], "facultad": facultad["nombre"]},
        "datos": {"titulo": "Convocatoria IA", "inscripcion_inicio": "2027-01-10", "inscripcion_fin": "2027-02-10", "modalidad_ingreso": "examen"},
        "evidencia": {"titulo": "CONVOCATORIA", "inscripcion_inicio": "se abren el 10 de enero de 2027", "inscripcion_fin": "cierran el 10 de febrero de 2027",
                      "modalidad_ingreso": "CONVOCATORIA"},
    }]}


@pytest.fixture()
def con_clave(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "clave-falsa-de-prueba")
    llamadas = []

    def falsa(cuerpo, modelo):
        llamadas.append(cuerpo)
        return _respuesta(falsa.propuesta)

    monkeypatch.setattr(lector_ia, "_llamar_gemini", falsa)
    falsa.llamadas = llamadas
    return falsa


def _subir(client, admin, nombre="convocatoria.pdf", contenido=PDF):
    return client.post("/api/admin/ia/leer", headers=admin, files={"archivo": (nombre, contenido, "application/octet-stream")})


def test_sin_clave_el_boton_no_se_activa_y_leer_explica_por_que(client, admin, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    assert client.get("/api/admin/ia/estado", headers=admin).json() == {"disponible": False, "modelo": None}
    r = _subir(client, admin)
    assert r.status_code == 503 and "GEMINI_API_KEY" in r.json()["detail"]


def test_con_clave_el_estado_no_revela_la_clave(client, admin, con_clave):
    datos = client.get("/api/admin/ia/estado", headers=admin).json()
    assert datos["disponible"] is True and datos["modelo"]
    assert "clave-falsa" not in json.dumps(datos)


def test_leer_devuelve_una_propuesta_y_no_guarda_nada(client, admin, con_clave):
    ref = client.get("/api/admin/referencias", headers=admin).json()["facultades"][0]
    con_clave.propuesta = _propuesta(ref)
    antes = len(client.get("/api/convocatorias").json())
    r = _subir(client, admin)
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["propuesta"]["origen"].startswith("Gemini") and datos["propuesta"]["fuente"] == "convocatoria.pdf"
    assert len(client.get("/api/convocatorias").json()) == antes  # la IA no escribe en la base
    enviado = con_clave.llamadas[0]
    assert enviado["generationConfig"]["temperature"] == 0
    assert "clave-falsa" not in json.dumps(enviado)  # la clave viaja en el encabezado, no en el contenido
    assert "evidencia" in enviado["systemInstruction"]["parts"][0]["text"]


def test_lo_que_propone_la_ia_pasa_por_el_analisis_y_el_verificador(client, admin, con_clave):
    ref = client.get("/api/admin/referencias", headers=admin).json()["facultades"][0]
    con_clave.propuesta = _propuesta(ref)
    propuesta = _subir(client, admin).json()["propuesta"]
    texto = "CONVOCATORIA. Las inscripciones se abren el 10 de enero de 2027 y cierran el 10 de febrero de 2027."
    analisis = client.post("/api/admin/propuestas/analizar", headers=admin, json={**propuesta, "texto_fuente": texto}).json()
    assert analisis["cambios"][0]["semaforo"] == "verde"
    inventada = json.loads(json.dumps(propuesta))
    inventada["cambios"][0]["evidencia"]["inscripcion_fin"] = "cierran el 28 de febrero de 2027"
    malo = client.post("/api/admin/propuestas/analizar", headers=admin, json={**inventada, "texto_fuente": texto}).json()
    assert malo["cambios"][0]["semaforo"] == "rojo"


def test_acepta_json_dentro_de_un_bloque_de_codigo():
    respuesta = {"candidates": [{"content": {"parts": [{"text": '```json\n{"formato": 1, "cambios": []}\n```'}]}}]}
    assert lector_ia._extraer_json(respuesta) == {"formato": 1, "cambios": []}


@pytest.mark.parametrize("respuesta", [
    {}, {"candidates": []}, {"promptFeedback": {"blockReason": "SAFETY"}},
    {"candidates": [{"content": {"parts": [{"text": "no es json"}]}}]},
    {"candidates": [{"content": {"parts": [{"text": "[1, 2]"}]}}]},
])
def test_respuestas_raras_de_la_ia_dan_un_error_claro(respuesta):
    with pytest.raises(ServicioNoDisponible) as e:
        lector_ia._extraer_json(respuesta)
    assert e.value.estado == 502


def test_archivos_no_validos_se_rechazan_antes_de_llamar_a_la_ia(client, admin, con_clave):
    assert _subir(client, admin, "virus.exe").status_code == 422
    assert _subir(client, admin, "vacio.pdf", b"").status_code == 422
    assert _subir(client, admin, "grande.pdf", b"0" * (lector_ia.MAX_BYTES + 1)).status_code == 413
    assert con_clave.llamadas == []


def test_un_error_de_gemini_llega_como_mensaje_y_no_como_caida(client, admin, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "clave-falsa-de-prueba")

    def falla(*_):
        raise ServicioNoDisponible("Se alcanzó el límite gratis de Gemini.", 429)

    monkeypatch.setattr(lector_ia, "_llamar_gemini", falla)
    r = _subir(client, admin)
    assert r.status_code == 429 and "límite" in r.json()["detail"]


def test_el_ejemplo_funciona_sin_clave_y_el_verificador_marca_el_error_a_proposito(client, admin, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    ejemplo = client.get("/api/admin/ia/ejemplo", headers=admin).json()
    assert ejemplo["ejemplo"] is True
    analisis = client.post("/api/admin/propuestas/analizar", headers=admin,
                           json={**ejemplo["propuesta"], "texto_fuente": ejemplo["texto_fuente"]}).json()
    cambio = analisis["cambios"][0]
    assert cambio["valido"] and cambio["semaforo"] == "rojo"  # la fecha del examen no coincide con el documento
    campos = {d["campo"]: d for d in cambio["diff"]}
    assert campos["fecha_examen"]["cita"] == "no_encontrada" and campos["costo_inscripcion_bs"]["cita"] == "encontrada"


def test_la_ia_exige_ser_administrador(client):
    assert client.get("/api/admin/ia/estado").status_code == 401
    assert client.get("/api/admin/ia/ejemplo").status_code == 401
    assert client.post("/api/admin/ia/leer", files={"archivo": ("a.pdf", PDF)}).status_code == 401


def test_si_un_modelo_esta_saturado_se_prueba_el_siguiente(client, admin, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "clave-falsa-de-prueba")
    monkeypatch.setattr(config, "GEMINI_MODELO", "modelo-a")
    monkeypatch.setattr(config, "GEMINI_RESPALDOS", ["modelo-b", "modelo-c"])
    ref = client.get("/api/admin/referencias", headers=admin).json()["facultades"][0]
    intentos = []

    def algunos(cuerpo, modelo):
        intentos.append(modelo)
        if modelo == "modelo-a":
            raise ServicioNoDisponible("saturado", 503, reintentable=True)
        return _respuesta(_propuesta(ref))

    monkeypatch.setattr(lector_ia, "_llamar_gemini", algunos)
    r = _subir(client, admin)
    assert r.status_code == 200 and intentos == ["modelo-a", "modelo-b"]
    assert r.json()["propuesta"]["origen"] == "Gemini (modelo-b)"  # se dice cuál modelo respondió de verdad


def test_si_todos_los_modelos_fallan_el_mensaje_es_claro(client, admin, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "clave-falsa-de-prueba")

    def saturado(cuerpo, modelo):
        raise ServicioNoDisponible("saturado", 503, reintentable=True)

    monkeypatch.setattr(lector_ia, "_llamar_gemini", saturado)
    r = _subir(client, admin)
    assert r.status_code == 503 and "saturados" in r.json()["detail"]


def test_un_error_de_clave_no_prueba_otros_modelos(client, admin, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "clave-falsa-de-prueba")
    intentos = []

    def mala_clave(cuerpo, modelo):
        intentos.append(modelo)
        raise ServicioNoDisponible("clave rechazada", 502)  # no es reintentable

    monkeypatch.setattr(lector_ia, "_llamar_gemini", mala_clave)
    assert _subir(client, admin).status_code == 502 and len(intentos) == 1


# ---------- limpieza de lo que devuelve la IA (antes un detalle tumbaba toda la propuesta) ----------

def test_la_limpieza_arregla_singulares_ids_de_texto_y_descarta_lo_que_no_sirve():
    cambios, avisos = lector_ia._sanear({"cambios": [
        {"accion": "Crear", "recurso": "Convocatoria", "datos": {"titulo": "A"}, "evidencia": "texto suelto"},
        {"accion": "actualizar", "recurso": "carreras", "id": "7", "datos": {"duracion_anios": 5}},
        {"accion": "actualizar", "recurso": "carreras", "datos": {"nombre": "Sin id"}},
        {"accion": "crear", "recurso": "embajadores", "datos": {"nombre": "No permitido"}},
        {"accion": "crear", "recurso": "carreras", "datos": {}},
        "no soy un cambio",
    ]})
    assert [(c["accion"], c["recurso"]) for c in cambios] == [("crear", "convocatorias"), ("actualizar", "carreras"), ("crear", "carreras")]
    assert cambios[0]["evidencia"] == {} and cambios[1]["id"] == 7
    texto = " ".join(avisos)
    assert "sin indicar cuál" in texto and "embajadores" in texto and "no traía datos" in texto and "formato no válido" in texto


def test_una_propuesta_con_un_cambio_malo_igual_se_puede_revisar(client, admin, con_clave):
    ref = client.get("/api/admin/referencias", headers=admin).json()["facultades"][0]
    buena = _propuesta(ref)
    buena["cambios"][0]["recurso"] = "convocatoria"  # singular: antes hacía fallar todo
    buena["cambios"].append({"accion": "crear", "recurso": "usuarios", "datos": {"x": 1}})
    con_clave.propuesta = {"formato": "1", **buena}  # incluso el formato como texto
    datos = _subir(client, admin).json()
    assert datos["propuesta"]["formato"] == 1 and len(datos["propuesta"]["cambios"]) == 1
    assert any("usuarios" in a for a in datos["avisos"])
    r = client.post("/api/admin/propuestas/analizar", headers=admin, json=datos["propuesta"])
    assert r.status_code == 200 and r.json()["total"] == 1  # ya no da 422


def test_si_la_ia_no_encuentra_nada_util_el_mensaje_es_claro(client, admin, con_clave):
    con_clave.propuesta = {"formato": 1, "cambios": [{"accion": "crear", "recurso": "convocatorias", "datos": {}}]}
    r = _subir(client, admin)
    assert r.status_code == 422 and "no encontró" in r.json()["detail"]
