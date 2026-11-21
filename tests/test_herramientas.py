"""Las herramientas de medición y el extractor por reglas (sin IA)."""
import json

import pytest

from backend.tools import extractor_reglas as extractor
from backend.tools import medir

TEXTO = """
CONVOCATORIA DE INGRESO 2027 - FACULTAD DE INGENIERÍA
Las inscripciones se realizarán del 10 de enero al 10 de febrero de 2027.
El examen de ingreso será el 20 de febrero de 2027. Los postulantes también pueden ingresar
por el curso preuniversitario. Costo de inscripción: Bs 150.
"""


def test_el_extractor_encuentra_fechas_y_monto_con_su_cita():
    p = extractor.extraer(TEXTO, anio=2027, referencias={"universidad": "UPE", "facultad": "Facultad de Ingeniería"})
    c = p["cambios"][0]
    assert c["datos"]["inscripcion_inicio"] == "2027-01-10"  # el año se toma del cierre
    assert c["datos"]["inscripcion_fin"] == "2027-02-10"
    assert c["datos"]["fecha_examen"] == "2027-02-20"
    assert c["datos"]["costo_inscripcion_bs"] == 150
    assert c["datos"]["modalidad_ingreso"] == "ambos"
    assert "10 de febrero" in c["evidencia"]["inscripcion_fin"] and "Bs 150" in c["evidencia"]["costo_inscripcion_bs"]
    assert c["referencias"]["facultad"] == "Facultad de Ingeniería"


def test_entiende_fechas_numericas_y_montos_con_miles():
    p = extractor.extraer("Inscripción del 10/01/2027 al 10/02/2027. Examen: 20/02/2027. Arancel de inscripción Bs. 1.200")
    d = p["cambios"][0]["datos"]
    assert (d["inscripcion_inicio"], d["inscripcion_fin"], d["fecha_examen"]) == ("2027-01-10", "2027-02-10", "2027-02-20")
    assert d["costo_inscripcion_bs"] == 1200


def test_si_no_entiende_algo_lo_deja_fuera_en_vez_de_adivinar():
    p = extractor.extraer("Pronto abriremos la convocatoria. Más información en la secretaría.")
    d = p["cambios"][0]["datos"]
    assert "inscripcion_inicio" not in d and "fecha_examen" not in d and "costo_inscripcion_bs" not in d
    assert p["cambios"][0]["confianza"] == "baja"


def test_fechas_imposibles_o_al_reves_no_se_proponen():
    p = extractor.extraer("Inscripciones del 31 de febrero al 40 de marzo de 2027.")
    assert "inscripcion_inicio" not in p["cambios"][0]["datos"]
    p = extractor.extraer("Inscripciones del 20 de marzo de 2027 al 10 de marzo de 2027.")
    assert "inscripcion_fin" not in p["cambios"][0]["datos"]


def test_una_propuesta_del_extractor_pasa_por_el_panel(client, admin):
    p = extractor.extraer(TEXTO, anio=2027, referencias={"universidad": "UPE", "facultad": "Facultad de Derecho"}, fuente="convocatoria.pdf")
    analisis = client.post("/api/admin/propuestas/analizar", json=p, headers=admin).json()
    advertencias = analisis["cambios"][0]["advertencias"]
    assert analisis["validos"] == 1
    # Los datos de ejemplo ya tienen una convocatoria con ese título: el panel lo avisa en vez de duplicar en silencio.
    assert len(advertencias) == 1 and "Ya existe uno con el mismo nombre" in advertencias[0]


def _crear_pdf(lineas):
    """PDF mínimo pero válido (con su tabla de posiciones), para probar la lectura sin depender de archivos."""
    contenido = b""
    if lineas:
        contenido = ("BT /F1 12 Tf 50 700 Td " + " ".join(f"({l}) Tj 0 -16 Td" for l in lineas) + " ET").encode()
    pagina = b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
    pagina += b"/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>" if lineas else b">>"
    objetos = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        pagina,
        b"<</Length %d>>\nstream\n" % len(contenido) + contenido + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    salida, posiciones = b"%PDF-1.4\n", []
    for i, objeto in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += b"%d 0 obj\n" % i + objeto + b"\nendobj\n"
    inicio_tabla = len(salida)
    salida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    salida += b"".join(b"%010d 00000 n \n" % p for p in posiciones)
    salida += b"trailer<</Root 1 0 R/Size %d>>\nstartxref\n%d\n%%%%EOF\n" % (len(objetos) + 1, inicio_tabla)
    return salida


def test_leer_un_pdf_con_texto(tmp_path):
    pdf = tmp_path / "c.pdf"
    pdf.write_bytes(_crear_pdf(["Inscripciones del 10 de enero al 10 de febrero de 2027", "Costo de inscripcion Bs 150"]))
    texto = extractor.leer_texto(pdf)
    assert "10 de enero" in texto and "Bs 150" in texto


def test_un_pdf_sin_texto_da_un_mensaje_claro(tmp_path):
    vacio = tmp_path / "escaneado.pdf"
    vacio.write_bytes(_crear_pdf([]))
    with pytest.raises(ValueError, match="escaneada"):
        extractor.leer_texto(vacio)


# ---------- medición ----------

VERDAD = {"formato": 1, "cambios": [{
    "accion": "crear", "recurso": "convocatorias",
    "datos": {"titulo": "Convocatoria 2027", "inscripcion_inicio": "2027-01-10", "inscripcion_fin": "2027-02-10",
              "fecha_examen": "2027-02-20", "costo_inscripcion_bs": 150},
}]}


def _propuesta(**datos):
    base = {"titulo": "Convocatoria 2027", "inscripcion_inicio": "2027-01-10", "inscripcion_fin": "2027-02-10",
            "fecha_examen": "2027-02-20", "costo_inscripcion_bs": 150}
    base.update(datos)
    return {"formato": 1, "cambios": [{"accion": "crear", "recurso": "convocatorias", "datos": base,
                                       "evidencia": {"inscripcion_fin": "cita", "fecha_examen": "cita"}}]}


def test_medir_perfecto():
    r = medir.comparar(_propuesta(), VERDAD)
    assert r["cobertura"] == 1.0 and r["precision"] == 1.0 and r["errores"] == []
    assert r["totales"]["con_cita"] == 2 and r["con_cita"] == 0.4


def test_medir_cuenta_errores_omisiones_e_inventos():
    propuesta = _propuesta(fecha_examen="2027-02-21", costo_inscripcion_bs=None)
    del propuesta["cambios"][0]["datos"]["costo_inscripcion_bs"]
    propuesta["cambios"][0]["datos"]["requisitos"] = "algo inventado"
    r = medir.comparar(propuesta, VERDAD)
    t = r["totales"]
    assert (t["esperados"], t["correctos"], t["incorrectos"], t["omitidos"], t["inventados"]) == (5, 3, 1, 1, 1)
    assert r["errores"][0] == {"cambio": "Convocatoria 2027", "campo": "fecha_examen", "esperado": "2027-02-20", "obtenido": "2027-02-21"}
    assert r["cobertura"] == 0.6 and r["precision"] == 0.75


def test_medir_ignora_mayusculas_acentos_y_tipos_numericos():
    verdad = {"formato": 1, "cambios": [{"accion": "crear", "recurso": "universidades", "datos": {"nombre": "Universidad Pública", "costo_mensual_bs": 50}}]}
    propuesta = {"formato": 1, "cambios": [{"accion": "crear", "recurso": "universidades", "datos": {"nombre": "UNIVERSIDAD PUBLICA", "costo_mensual_bs": 50.0}}]}
    assert medir.comparar(propuesta, verdad)["cobertura"] == 1.0


def test_medir_sin_propuesta_todo_queda_sin_encontrar():
    r = medir.comparar({"formato": 1, "cambios": []}, VERDAD)
    assert r["totales"]["omitidos"] == 5 and r["cobertura"] == 0.0 and r["precision"] is None


def test_la_linea_de_comandos_imprime_un_informe(tmp_path, capsys):
    a, b = tmp_path / "p.json", tmp_path / "v.json"
    a.write_text(json.dumps(_propuesta()), encoding="utf-8")
    b.write_text(json.dumps(VERDAD), encoding="utf-8")
    assert medir.main([str(a), str(b)]) == 0
    salida = capsys.readouterr().out
    assert "Cobertura" in salida and "100%" in salida
