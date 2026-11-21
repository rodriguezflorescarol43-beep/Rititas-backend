"""El Detective de datos y la importación de propuestas (IA solo para el administrador)."""
from datetime import date, timedelta

import pytest

from backend.app.services import revision


def _claves(datos):
    return {h["regla"] for h in datos["hallazgos"]}


UNI = {"nombre": "Universidad X", "sigla": "UX", "tipo": "publica", "ciudad": "Oruro", "departamento": "Oruro"}


# ---------- Detective ----------

def test_el_detective_exige_ser_administrador(client):
    assert client.get("/api/admin/revision").status_code == 401


def test_el_detective_ordena_y_no_filtra_campos_internos(client, admin):
    datos = client.get("/api/admin/revision", headers=admin).json()
    assert datos["hallazgos"] and set(datos["resumen"]) == {"alta", "media", "baja"}
    orden = {"alta": 0, "media": 1, "baja": 2}
    niveles = [orden[h["severidad"]] for h in datos["hallazgos"]]
    assert niveles == sorted(niveles)
    assert all("_orden" not in h and h["sugerencia"] and h["detalle"] for h in datos["hallazgos"])


def test_los_datos_de_ejemplo_no_generan_falsos_duplicados(client, admin):
    datos = client.get("/api/admin/revision", headers=admin).json()
    assert "posible_duplicado" not in _claves(datos)


def test_lo_que_cierra_pronto_y_no_esta_verificado_es_urgente(session):
    # La convocatoria de Ingeniería (UPE) cierra a los 12 días: dentro de 8 días quedan 4.
    datos = revision.revisar(session, hoy=date.today() + timedelta(days=8))
    urgentes = [h for h in datos["hallazgos"] if h["severidad"] == "alta" and h["regla"] == "sin_verificar"]
    assert any("Ingeniería" in h["titulo"] for h in urgentes)


def test_detecta_examen_antes_de_abrir_la_inscripcion(client, admin):
    facultad = client.get("/api/admin/facultades", headers=admin).json()[0]
    hoy = date.today()
    client.post("/api/admin/convocatorias", headers=admin, json={
        "facultad_id": facultad["id"], "titulo": "Rara", "modalidad_ingreso": "examen",
        "inscripcion_inicio": (hoy + timedelta(days=30)).isoformat(),
        "inscripcion_fin": (hoy + timedelta(days=60)).isoformat(),
        "fecha_examen": (hoy + timedelta(days=10)).isoformat(),
    })
    datos = client.get("/api/admin/revision", headers=admin).json()
    assert any(h["regla"] == "fechas_raras" and h["severidad"] == "alta" for h in datos["hallazgos"])


def test_detecta_costos_atipicos_comparando_con_sus_pares(client, admin):
    for i, costo in enumerate((45, 50, 55)):
        client.post("/api/admin/universidades", headers=admin, json={**UNI, "nombre": f"Pública {chr(65 + i)}", "sigla": f"P{i}", "ciudad": f"Ciudad {i}", "costo_mensual_bs": costo})
    client.post("/api/admin/universidades", headers=admin, json={**UNI, "nombre": "Pública Barata", "sigla": "PB", "ciudad": "Otra", "costo_mensual_bs": 2})
    datos = client.get("/api/admin/revision", headers=admin).json()
    assert any(h["regla"] == "costo_atipico" and "Pública Barata" in h["titulo"] for h in datos["hallazgos"])


def test_detecta_posibles_duplicados_en_la_misma_ciudad(client, admin):
    client.post("/api/admin/universidades", headers=admin, json={**UNI, "nombre": "Universidad Pública Ejemplo", "sigla": "UPE2", "ciudad": "Cochabamba", "departamento": "Cochabamba"})
    datos = client.get("/api/admin/revision", headers=admin).json()
    assert any(h["regla"] == "posible_duplicado" and h["recurso"] == "universidades" for h in datos["hallazgos"])


# ---------- Importar propuesta ----------

def _propuesta(**extra):
    return {
        "formato": 1,
        "origen": "prueba",
        "fuente": "https://upe.example/convocatorias/ingenieria.pdf",
        "cambios": [{
            "accion": "crear", "recurso": "convocatorias",
            "referencias": {"universidad": "UPE", "facultad": "Facultad de Derecho"},
            "datos": {
                "titulo": "Convocatoria 2027", "inscripcion_inicio": "2027-01-10", "inscripcion_fin": "2027-02-10",
                "fecha_examen": "2027-02-20", "modalidad_ingreso": "examen", "costo_inscripcion_bs": 150,
            },
            "evidencia": {
                "inscripcion_inicio": "Las inscripciones se abren el 10 de enero de 2027",
                "inscripcion_fin": "y cierran el 10 de febrero",
                "fecha_examen": "El examen será el 20 de febrero",
                "costo_inscripcion_bs": "Costo de inscripción: Bs 150",
                "titulo": "Convocatoria de ingreso 2027",
                "modalidad_ingreso": "ingreso por examen",
            },
        }],
        **extra,
    }


def test_analizar_no_escribe_nada_y_muestra_el_antes_y_el_despues(client, admin):
    antes = len(client.get("/api/convocatorias").json())
    r = client.post("/api/admin/propuestas/analizar", json=_propuesta(), headers=admin)
    assert r.status_code == 200
    cambio = r.json()["cambios"][0]
    assert cambio["valido"] and not cambio["errores"]
    campos = {d["campo"]: d for d in cambio["diff"]}
    assert campos["inscripcion_fin"]["despues"] == "2027-02-10" and campos["inscripcion_fin"]["evidencia"]
    assert "facultad_id" in campos  # la referencia por nombre se resolvió
    assert len(client.get("/api/convocatorias").json()) == antes


def test_analizar_avisa_de_problemas_sin_inventar_nada(client, admin):
    p = _propuesta()
    p["cambios"][0]["datos"]["inventado"] = "x"
    del p["cambios"][0]["evidencia"]["costo_inscripcion_bs"]
    cambio = client.post("/api/admin/propuestas/analizar", json=p, headers=admin).json()["cambios"][0]
    texto = " ".join(cambio["advertencias"])
    assert "inventado" in texto and "Sin cita de la fuente: costo_inscripcion_bs" in texto


def test_analizar_marca_errores_de_datos_y_de_referencias(client, admin):
    p = _propuesta()
    p["cambios"][0]["datos"]["inscripcion_fin"] = "2026-12-01"  # antes del inicio
    malo = client.post("/api/admin/propuestas/analizar", json=p, headers=admin).json()["cambios"][0]
    assert not malo["valido"] and "terminar antes" in " ".join(malo["errores"])

    p = _propuesta()
    p["cambios"][0]["referencias"]["facultad"] = "Facultad que no existe"
    sin_padre = client.post("/api/admin/propuestas/analizar", json=p, headers=admin).json()["cambios"][0]
    assert not sin_padre["valido"] and "No encontré la facultad" in sin_padre["errores"][0]


def test_la_ia_no_puede_tocar_datos_personales_ni_pasarse_de_tamano(client, admin):
    for recurso in ("embajadores", "mensajes", "usuarios"):
        p = _propuesta()
        p["cambios"][0]["recurso"] = recurso
        assert client.post("/api/admin/propuestas/analizar", json=p, headers=admin).status_code == 422
    grande = _propuesta()
    grande["cambios"] = grande["cambios"] * 51
    assert client.post("/api/admin/propuestas/analizar", json=grande, headers=admin).status_code == 422
    assert client.post("/api/admin/propuestas/analizar", json={"formato": 2, "cambios": []}, headers=admin).status_code == 422


def test_aplicar_crea_anota_verificacion_fuente_e_historial(client, admin):
    version = client.get("/api/paquete").json()["version"]
    r = client.post("/api/admin/propuestas/aplicar", headers=admin, json={"propuesta": _propuesta(), "aprobados": [{"indice": 0}]})
    assert r.status_code == 200 and len(r.json()["aplicados"]) == 1
    creada = next(c for c in client.get("/api/convocatorias").json() if c["titulo"] == "Convocatoria 2027")
    assert creada["verificado_en"] == date.today().isoformat()
    assert creada["fuente_url"] == "https://upe.example/convocatorias/ingenieria.pdf"
    historial = client.get("/api/admin/registro", headers=admin).json()
    assert historial[0]["accion"] == "crear" and historial[0]["evidencia"]["fecha_examen"]
    assert client.get("/api/paquete").json()["version"] > version  # el celular se entera del cambio


def test_si_la_fuente_es_un_archivo_se_guarda_en_el_historial_no_como_enlace(client, admin):
    p = _propuesta(fuente="afiche_instituto.jpg")
    client.post("/api/admin/propuestas/aplicar", headers=admin, json={"propuesta": p, "aprobados": [{"indice": 0}]})
    creada = next(c for c in client.get("/api/convocatorias").json() if c["titulo"] == "Convocatoria 2027")
    assert creada["fuente_url"] is None and creada["verificado_en"] == date.today().isoformat()
    assert client.get("/api/admin/registro", headers=admin).json()[0]["fuente"] == "afiche_instituto.jpg"


def test_actualizar_aplica_solo_los_campos_aprobados(client, admin):
    conv = client.get("/api/admin/convocatorias", headers=admin).json()[0]
    p = {"formato": 1, "fuente": "https://upe.example/c.pdf", "cambios": [{
        "accion": "actualizar", "recurso": "convocatorias", "id": conv["id"],
        "datos": {"inscripcion_fin": (date.fromisoformat(conv["inscripcion_fin"]) + timedelta(days=5)).isoformat(), "costo_inscripcion_bs": 999},
        "evidencia": {"inscripcion_fin": "ampliada", "costo_inscripcion_bs": "Bs 999"},
    }]}
    analisis = client.post("/api/admin/propuestas/analizar", json=p, headers=admin).json()["cambios"][0]
    assert {d["campo"] for d in analisis["diff"] if d["cambia"]} == {"inscripcion_fin", "costo_inscripcion_bs"}

    r = client.post("/api/admin/propuestas/aplicar", headers=admin, json={"propuesta": p, "aprobados": [{"indice": 0, "campos": ["inscripcion_fin"]}]})
    assert len(r.json()["aplicados"]) == 1
    despues = next(c for c in client.get("/api/admin/convocatorias", headers=admin).json() if c["id"] == conv["id"])
    assert despues["inscripcion_fin"] != conv["inscripcion_fin"]
    assert despues["costo_inscripcion_bs"] == conv["costo_inscripcion_bs"]  # el rechazado no se tocó
    registro = client.get("/api/admin/registro", headers=admin).json()[0]
    assert registro["antes"] == {"inscripcion_fin": conv["inscripcion_fin"]} and "costo_inscripcion_bs" not in registro["despues"]


def test_lo_no_aprobado_o_con_errores_no_se_aplica(client, admin):
    malo = _propuesta()["cambios"][0]
    malo["datos"] = {**malo["datos"], "titulo": "Mala", "inscripcion_fin": "2026-12-01"}
    p = _propuesta()
    p["cambios"].append(malo)
    r = client.post("/api/admin/propuestas/aplicar", headers=admin, json={"propuesta": p, "aprobados": [{"indice": 1}, {"indice": 7}]})
    datos = r.json()
    assert datos["aplicados"] == [] and len(datos["omitidos"]) == 2
    titulos = [c["titulo"] for c in client.get("/api/convocatorias").json()]
    assert "Mala" not in titulos and "Convocatoria 2027" not in titulos  # el índice 0 nunca se aprobó
    assert client.post("/api/admin/propuestas/aplicar", headers=admin, json={"propuesta": p, "aprobados": []}).status_code == 422


def test_el_ejemplo_de_la_documentacion_es_valido(client, admin):
    """Si el formato cambia y el ejemplo queda desactualizado, esta prueba avisa."""
    import json
    from pathlib import Path

    ejemplo = json.loads((Path(__file__).resolve().parents[1] / "docs" / "ejemplo-propuesta.json").read_text(encoding="utf-8"))
    analisis = client.post("/api/admin/propuestas/analizar", json=ejemplo, headers=admin).json()
    assert analisis["total"] == 2 and analisis["con_errores"] == 0
    assert all(not c["advertencias"] for c in analisis["cambios"]), [c["advertencias"] for c in analisis["cambios"]]


def test_las_referencias_traen_los_numeros_internos(client, admin):
    ref = client.get("/api/admin/referencias", headers=admin).json()
    assert ref["universidades"][0]["id"] and ref["facultades"][0]["universidad"] and ref["convocatorias"][0]["inscripcion_fin"]


@pytest.mark.parametrize("ruta,metodo", [
    ("/api/admin/referencias", "get"), ("/api/admin/registro", "get"),
    ("/api/admin/propuestas/analizar", "post"), ("/api/admin/propuestas/aplicar", "post"),
])
def test_todo_exige_ser_administrador(client, ruta, metodo):
    r = getattr(client, metodo)(ruta, **({"json": {}} if metodo == "post" else {}))
    assert r.status_code == 401
