"""Verificador de citas (detector de datos inventados) y medición de la IA desde el panel."""
import copy

from backend.app.services import verificador

DOCUMENTO = """CONVOCATORIA DE INGRESO 2027 - FACULTAD DE INGENIERÍA
Las inscripciones se abren el 10 de enero de 2027 y cierran el 10 de febrero de 2027.
El examen de ingreso será el 20 de febrero de 2027. Costo de inscripción: Bs 150."""


def _propuesta(**extra):
    return {
        "formato": 1, "origen": "Claude", "fuente": "https://upe.example/ingenieria.pdf",
        "cambios": [{
            "accion": "crear", "recurso": "convocatorias",
            "referencias": {"universidad": "UPE", "facultad": "Facultad de Ingeniería"},
            "datos": {"titulo": "Convocatoria 2027", "inscripcion_inicio": "2027-01-10", "inscripcion_fin": "2027-02-10",
                      "fecha_examen": "2027-02-20", "modalidad_ingreso": "examen", "costo_inscripcion_bs": 150},
            "evidencia": {
                "titulo": "CONVOCATORIA DE INGRESO 2027",
                "inscripcion_inicio": "Las inscripciones se abren el 10 de enero de 2027",
                "inscripcion_fin": "cierran el 10 de febrero de 2027",
                "fecha_examen": "El examen de ingreso será el 20 de febrero de 2027",
                "modalidad_ingreso": "El examen de ingreso",
                "costo_inscripcion_bs": "Costo de inscripción: Bs 150",
            },
        }],
        **extra,
    }


# ---------- reglas del verificador ----------

def test_la_cita_se_busca_sin_importar_mayusculas_acentos_ni_signos():
    doc = verificador.Documento(DOCUMENTO)
    assert doc.buscar("costo de INSCRIPCION bs. 150") == "encontrada"
    assert doc.buscar("Las inscripciones se abren el 10 de enero de 2027") == "encontrada"
    assert doc.buscar("Las inscripciones abren el 10 de enero") == "parecida"
    assert doc.buscar("Becas completas para todos los postulantes") == "no_encontrada"


def test_el_valor_debe_coincidir_con_su_cita():
    assert verificador.valor_coincide(150, "Costo de inscripción: Bs 150") is True
    assert verificador.valor_coincide(200, "Costo de inscripción: Bs 150") is False
    assert verificador.valor_coincide(1500, "Matrícula: Bs 1.500") is True
    assert verificador.valor_coincide(15, "Bs 150") is False
    assert verificador.valor_coincide("2027-02-10", "cierran el 10 de febrero") is True
    assert verificador.valor_coincide("2027-02-10", "cierran el 10/02/2027") is True
    assert verificador.valor_coincide("2027-02-11", "cierran el 10 de febrero de 2027") is False
    assert verificador.valor_coincide("2027-02-10", "cierran el 10 de febrero de 2026") is False
    assert verificador.valor_coincide("examen", "El examen") is None  # textos: no se puede saber


# ---------- en el panel ----------

def test_con_el_documento_todo_queda_en_verde(client, admin):
    r = client.post("/api/admin/propuestas/analizar", json=_propuesta(texto_fuente=DOCUMENTO), headers=admin).json()
    cambio = r["cambios"][0]
    assert cambio["semaforo"] == "verde", cambio
    assert r["citas"]["con_texto"] and r["citas"]["no_encontradas"] == 0 and r["semaforo"]["verde"] == 1
    assert all(d["cita"] == "encontrada" for d in cambio["diff"] if d["evidencia"])


def test_detecta_una_cita_inventada_y_un_valor_que_no_coincide(client, admin):
    p = _propuesta(texto_fuente=DOCUMENTO)
    p["cambios"][0]["evidencia"]["fecha_examen"] = "El examen será el 25 de febrero de 2027"  # no está en el documento
    p["cambios"][0]["datos"]["costo_inscripcion_bs"] = 200  # la cita dice 150
    cambio = client.post("/api/admin/propuestas/analizar", json=p, headers=admin).json()["cambios"][0]
    assert cambio["semaforo"] == "rojo" and cambio["valido"]  # se puede aprobar, pero se avisa fuerte
    campos = {d["campo"]: d for d in cambio["diff"]}
    assert campos["fecha_examen"]["cita"] == "no_encontrada"
    assert campos["costo_inscripcion_bs"]["valor_coincide"] is False
    avisos = " ".join(cambio["advertencias"])
    assert "posible dato inventado" in avisos and "no coincide" in avisos


def test_sin_documento_queda_en_amarillo_y_con_errores_en_rojo(client, admin):
    sin_texto = client.post("/api/admin/propuestas/analizar", json=_propuesta(), headers=admin).json()
    assert sin_texto["cambios"][0]["semaforo"] == "amarillo" and not sin_texto["citas"]["con_texto"]
    malo = _propuesta(texto_fuente=DOCUMENTO)
    malo["cambios"][0]["datos"]["inscripcion_fin"] = "2026-01-01"
    assert client.post("/api/admin/propuestas/analizar", json=malo, headers=admin).json()["cambios"][0]["semaforo"] == "rojo"


def test_el_texto_del_documento_no_puede_ser_gigante(client, admin):
    r = client.post("/api/admin/propuestas/analizar", json=_propuesta(texto_fuente="a" * 300_001), headers=admin)
    assert r.status_code == 422


# ---------- medición ----------

def _verdad():
    v = copy.deepcopy(_propuesta())
    v["cambios"][0].pop("evidencia")
    return v


def test_medir_una_ia_perfecta_contra_las_reglas(client, admin):
    r = client.post("/api/admin/mediciones", headers=admin, json={
        "documento": "Ingeniería 2027", "texto_fuente": DOCUMENTO, "propuesta": _propuesta(), "verdad": _verdad(),
    })
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["ia"]["precision"] == 1 and datos["ia"]["cobertura"] == 1 and datos["ia"]["inventados"] == 0
    assert datos["reglas"]["esperados"] == datos["ia"]["esperados"]
    assert datos["reglas"]["correctos"] < datos["ia"]["correctos"]  # las reglas no saben el título
    assert datos["verificador"] == {"errores": 0, "detectados": 0, "correctos": 6, "falsas_alarmas": 0}


def test_medir_cuenta_errores_inventos_y_lo_que_atrapo_el_verificador(client, admin):
    ia = _propuesta()
    ia["cambios"][0]["datos"]["costo_inscripcion_bs"] = 200  # error: la cita dice 150 → el verificador lo marca
    ia["cambios"][0]["datos"]["fecha_examen"] = "2027-02-25"
    ia["cambios"][0]["evidencia"]["fecha_examen"] = "El examen será el 25 de febrero"  # cita inventada → marcado
    ia["cambios"][0]["datos"]["requisitos"] = "Fotocopia de carnet"  # inventado y sin cita → marcado
    datos = client.post("/api/admin/mediciones", headers=admin, json={
        "documento": "Ingeniería 2027", "texto_fuente": DOCUMENTO, "propuesta": ia, "verdad": _verdad(),
    }).json()
    assert datos["ia"]["incorrectos"] == 2 and datos["ia"]["inventados"] == 1
    assert datos["verificador"]["errores"] == 3 and datos["verificador"]["detectados"] == 3

    guardadas = client.get("/api/admin/mediciones", headers=admin).json()
    assert guardadas["mediciones"][0]["documento"] == "Ingeniería 2027"
    assert guardadas["total"]["documentos"] == 1 and guardadas["total"]["detectados"] == 3


def test_medir_sin_documento_no_inventa_numeros_de_reglas_ni_verificador(client, admin):
    datos = client.post("/api/admin/mediciones", headers=admin, json={
        "documento": "Afiche", "propuesta": _propuesta(), "verdad": _verdad(),
    }).json()
    assert datos["reglas"] is None and datos["verificador"] is None and datos["ia"]["precision"] == 1


def test_medir_valida_la_entrada_y_exige_administrador(client, admin):
    assert client.post("/api/admin/mediciones", json={}).status_code == 401
    assert client.get("/api/admin/mediciones").status_code == 401
    assert client.post("/api/admin/mediciones", headers=admin, json={"propuesta": {}, "verdad": _verdad()}).status_code == 422
    sin_nombre = {"propuesta": {k: v for k, v in _propuesta().items() if k != "fuente"}, "verdad": _verdad()}
    assert client.post("/api/admin/mediciones", headers=admin, json=sin_nombre).status_code == 422
