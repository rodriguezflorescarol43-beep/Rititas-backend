"""El motor del celular (JavaScript) debe dar lo MISMO que el del servidor (Python).

Si divergieran, la persona vería una recomendación distinta según si tiene señal o no.
Se ejecuta el código real de frontend/src/datos con Node. Se omite si Node no está instalado.
"""
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest
from sqlmodel import select

from backend.app.models.entities import Opcion, Pregunta

RAIZ = Path(__file__).resolve().parents[1]
MOTOR_DEL_CELULAR = RAIZ / "frontend" / "src" / "datos" / "motor.js"
pytestmark = [
    pytest.mark.skipif(shutil.which("node") is None, reason="Node no está instalado"),
    # El frontend vive en otro repositorio: clónalo en ./frontend para correr esta prueba.
    pytest.mark.skipif(not MOTOR_DEL_CELULAR.exists(), reason="Falta el frontend: clona su repositorio en ./frontend"),
]


def _casos(session):
    por_pregunta = []
    for p in session.exec(select(Pregunta).order_by(Pregunta.orden)):
        por_pregunta.append([o.id for o in session.exec(select(Opcion).where(Opcion.pregunta_id == p.id).order_by(Opcion.id))])
    todas = [i for fila in por_pregunta for i in fila]
    areas = {o.id: o.area for o in session.exec(select(Opcion))}
    base = []
    for posicion in range(4):
        base.append([fila[posicion] for fila in por_pregunta])  # siempre la 1.ª, 2.ª, 3.ª o 4.ª opción
    base.append([i for i in todas if areas[i] == "salud"])
    base.append([i for i in todas if areas[i] in ("tecnologia", "negocios")])
    base.append(todas[:5])
    condiciones = [
        {},
        {"departamento": "Cochabamba", "puede_mudarse": False},
        {"departamento": "Cochabamba", "presupuesto_max_bs": 45},
        {"departamento": "La Paz", "presupuesto_max_bs": 500, "puede_mudarse": True},
        {"departamento": "Oruro"},
        {"presupuesto_max_bs": 0},
    ]
    return [{"opciones": opciones, **extra} for opciones in base for extra in condiciones]


def _ejecutar(client, session):
    paquete = client.get("/api/paquete").json()
    clave = client.get("/api/paquete/clave").json()["clave_publica"]
    casos = _casos(session)
    hoy = date.today().isoformat()
    cond = {"departamento": "Cochabamba", "presupuesto_max_bs": 2000, "puede_mudarse": True, "vivienda_mensual_bs": 600}
    entrada = json.dumps({"paquete": json.loads(paquete["datos"]), "casos": casos, "hoy": hoy,
                          "firmado": paquete, "clave": clave, "condiciones": cond})
    salida = subprocess.run(
        ["node", str(RAIZ / "tests" / "js" / "paridad.mjs")],
        input=entrada, capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert salida.returncode == 0, salida.stderr
    return casos, json.loads(salida.stdout)


def test_el_celular_y_el_servidor_recomiendan_lo_mismo(client, session):
    casos, js = _ejecutar(client, session)
    assert len(casos) >= 40
    for caso, del_celular in zip(casos, js["resultados"]):
        del_servidor = client.post("/api/orientacion/resultado", json=caso).json()
        assert del_celular["areas"] == del_servidor["areas"], caso
        assert del_celular["aviso"] == del_servidor["aviso"]
        propias = [{k: v for k, v in r.items() if k != "razones"} for r in del_celular["recomendaciones"]]
        assert propias == del_servidor["recomendaciones"], caso


def test_el_estado_de_las_convocatorias_coincide(client, session):
    _, js = _ejecutar(client, session)
    del_servidor = {c["id"]: c for c in client.get("/api/convocatorias").json()}
    for c in js["convocatorias"]:
        assert c["estado"] == del_servidor[c["id"]]["estado"]
        assert c["dias_restantes"] == del_servidor[c["id"]]["dias_restantes"]


def test_el_navegador_comprueba_la_firma_igual_que_python(client, session):
    _, js = _ejecutar(client, session)
    assert js["firmaValida"] is True
    assert js["firmaAlteradaValida"] is False


def test_los_planes_son_coherentes(client, session):
    _, js = _ejecutar(client, session)
    planes = js["planes"]
    primera = client.post("/api/orientacion/resultado", json=_casos(session)[0]).json()["recomendaciones"][0]
    assert planes["A"]["carrera_id"] == primera["carrera_id"]  # el Plan A es la mejor recomendación

    for plan in (planes["A"], planes["B"]):
        if plan:
            assert plan["costo"]["total"] == sum(l["monto"] or 0 for l in plan["costo"]["lineas"])
            if plan["requiere_mudarse"]:
                assert any(l["clave"] == "vivienda" for l in plan["costo"]["lineas"])
    if planes["B"]:
        assert planes["B"]["mejoras"], "el Plan B solo se muestra si mejora algo"
        assert planes["B"]["carrera_id"] != planes["A"]["carrera_id"]
    assert planes["C"]["preuniversitario"] is not None
    assert planes["supuestos"] == {"meses": 10, "vivienda_mensual_bs": 600}
