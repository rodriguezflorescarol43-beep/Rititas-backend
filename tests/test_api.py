from sqlmodel import select

from backend.app.models.entities import Opcion


def test_salud(client):
    assert client.get("/api/salud").json() == {"estado": "ok"}


def test_ruta_api_desconocida_da_404_json(client):
    r = client.get("/api/no-existe")
    assert r.status_code == 404
    assert r.json()["detail"]


def test_meta_incluye_departamentos_y_areas(client):
    datos = client.get("/api/meta").json()
    assert "Cochabamba" in datos["departamentos"]
    assert "Potosí" in datos["departamentos"]  # solo tiene un instituto
    assert "salud" in datos["areas"]


def test_universidades_y_filtro_por_tipo(client):
    todas = client.get("/api/universidades").json()
    assert len(todas) == 4
    privadas = client.get("/api/universidades", params={"tipo": "privada"}).json()
    assert [u["sigla"] for u in privadas] == ["UPRE"]
    assert client.get("/api/universidades", params={"tipo": "otra"}).status_code == 422


def test_datos_de_ejemplo_no_estan_verificados(client):
    for u in client.get("/api/universidades").json():
        assert u["verificado_en"] is None


def test_facultades_traen_estado_de_convocatoria(client):
    facultades = client.get("/api/facultades").json()
    estados = {f["nombre"]: f["estado_convocatoria"] for f in facultades if f["universidad_sigla"] == "UPE"}
    assert estados["Facultad de Ingeniería"] == "abierta"
    assert estados["Facultad de Medicina y Salud"] == "proxima"
    assert estados["Facultad de Ciencias Económicas"] == "cerrada"


def test_detalle_de_facultad_abre_su_convocatoria(client):
    ing = next(f for f in client.get("/api/facultades").json() if f["nombre"] == "Facultad de Ingeniería")
    d = client.get(f"/api/facultades/{ing['id']}").json()
    assert d["universidad"]["sigla"] == "UPE"
    assert {c["nombre"] for c in d["carreras"]} == {"Ingeniería de Sistemas", "Ingeniería Civil"}
    assert d["convocatorias"][0]["estado"] == "abierta"
    assert d["convocatorias"][0]["dias_restantes"] == 12


def test_facultad_inexistente_da_404(client):
    assert client.get("/api/facultades/9999").status_code == 404


def test_convocatorias_filtradas_por_estado(client):
    abiertas = client.get("/api/convocatorias", params={"estado": "abierta"}).json()
    assert abiertas and all(c["estado"] == "abierta" for c in abiertas)
    assert client.get("/api/convocatorias", params={"estado": "x"}).status_code == 422


def test_preuniversitarios_por_departamento(client):
    r = client.get("/api/preuniversitarios", params={"departamento": "Potosí"}).json()
    assert len(r) == 1 and r[0]["tipo"] == "instituto"


def test_test_vocacional_tiene_8_preguntas_con_opciones(client):
    preguntas = client.get("/api/orientacion/preguntas").json()
    assert len(preguntas) == 8
    assert all(len(p["opciones"]) == 4 for p in preguntas)
    assert "area" not in preguntas[0]["opciones"][0]  # no se revela el área


def _ids_de_area(session, area):
    return [o.id for o in session.exec(select(Opcion).where(Opcion.area == area))]


def test_resultado_destaca_el_area_elegida(client, session):
    r = client.post("/api/orientacion/resultado", json={"opciones": _ids_de_area(session, "salud")})
    assert r.status_code == 200
    datos = r.json()
    assert datos["areas"][0] == {"area": "salud", "nombre": "Salud", "porcentaje": 100}
    nombres = {x["carrera"] for x in datos["recomendaciones"]}
    assert nombres == {"Medicina", "Enfermería"}
    assert all(x["motivo"] for x in datos["recomendaciones"])
    assert datos["aviso"]


def test_presupuesto_descarta_lo_caro(client, session):
    r = client.post("/api/orientacion/resultado", json={
        "opciones": _ids_de_area(session, "salud"), "presupuesto_max_bs": 45,
    }).json()
    assert {x["universidad"] for x in r["recomendaciones"]} == {"Universidad Pública Ejemplo del Norte"}


def test_si_no_puede_mudarse_solo_su_departamento(client, session):
    r = client.post("/api/orientacion/resultado", json={
        "opciones": _ids_de_area(session, "salud"),
        "departamento": "Cochabamba", "puede_mudarse": False,
    }).json()
    assert r["recomendaciones"]
    assert all(x["departamento"] == "Cochabamba" and not x["requiere_mudarse"] for x in r["recomendaciones"])


def test_mudarse_penaliza_y_se_explica(client, session):
    r = client.post("/api/orientacion/resultado", json={
        "opciones": _ids_de_area(session, "salud"), "departamento": "Cochabamba",
    }).json()
    primero, ultimo = r["recomendaciones"][0], r["recomendaciones"][-1]
    assert not primero["requiere_mudarse"]
    assert ultimo["requiere_mudarse"] and "mudarte" in ultimo["motivo"]


def test_resultado_sin_respuestas_validas_da_422(client):
    assert client.post("/api/orientacion/resultado", json={"opciones": []}).status_code == 422
    assert client.post("/api/orientacion/resultado", json={"opciones": [99999]}).status_code == 422


def test_contacto_guarda_y_valida(client):
    ok = client.post("/api/contacto", json={"nombre": "Ana", "email": "ana@ejemplo.com", "mensaje": "Hola, ¿hay becas?"})
    assert ok.status_code == 201 and ok.json()["nombre"] == "Ana"
    mal = client.post("/api/contacto", json={"nombre": "Ana", "email": "no-es-correo", "mensaje": "Hola, ¿hay becas?"})
    assert mal.status_code == 422
