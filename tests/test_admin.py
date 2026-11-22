import json
import time

from backend.app.core import security
from backend.app.services import medios

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100
MP4 = b"\x00\x00\x00\x18ftypisom" + b"0" * 100

UNIVERSIDAD = {
    "nombre": "Universidad Nueva", "sigla": "UN", "tipo": "publica",
    "ciudad": "Oruro", "departamento": "Oruro", "costo_mensual_bs": 30,
}


def _subir(client, admin, contenido, nombre="foto.png"):
    return client.post("/api/admin/media", files={"archivo": (nombre, contenido, "image/png")}, headers=admin)


# ---------- acceso ----------

def test_sin_token_no_se_entra(client):
    for ruta in ("/api/admin/resumen", "/api/admin/universidades", "/api/admin/media", "/api/admin/mensajes"):
        assert client.get(ruta).status_code == 401
    assert client.post("/api/admin/universidades", json=UNIVERSIDAD).status_code == 401
    assert client.delete("/api/admin/universidades/1").status_code == 401


def test_token_falso_o_alterado_no_sirve(client, admin):
    token = admin["Authorization"].split(" ")[1]
    for malo in ("basura", token[:-3] + "xyz", "a.b"):
        assert client.get("/api/admin/resumen", headers={"Authorization": f"Bearer {malo}"}).status_code == 401
    assert client.get("/api/admin/resumen", headers={"Authorization": token}).status_code == 401  # sin «Bearer»


def test_token_vence():
    token, expira = security.crear_token(ahora=1000)
    assert security.token_valido(token, ahora=1000)
    assert not security.token_valido(token, ahora=expira + 1)


def test_login_correcto_e_incorrecto(client):
    mal = client.post("/api/admin/login", json={"password": "otra"})
    assert mal.status_code == 401
    ok = client.post("/api/admin/login", json={"password": "clave-de-prueba"})
    assert ok.status_code == 200 and ok.json()["expira_en"] > time.time()


def test_demasiados_intentos_bloquean_aun_con_la_clave_buena(client):
    for _ in range(5):
        assert client.post("/api/admin/login", json={"password": "mal"}).status_code == 401
    assert client.post("/api/admin/login", json={"password": "clave-de-prueba"}).status_code == 429


# ---------- altas, cambios y bajas ----------

def test_resumen_cuenta_todo(client, admin):
    r = client.get("/api/admin/resumen", headers=admin).json()
    assert r["universidades"] == 4 and r["preuniversitarios"] == 5 and r["medios"] == 0


def test_crear_universidad_y_verla_en_la_pagina_publica(client, admin):
    r = client.post("/api/admin/universidades", json=UNIVERSIDAD, headers=admin)
    assert r.status_code == 201 and r.json()["id"]
    publicas = client.get("/api/universidades").json()
    assert "Universidad Nueva" in [u["nombre"] for u in publicas]


def test_actualizar_y_borrar(client, admin):
    nueva = client.post("/api/admin/universidades", json=UNIVERSIDAD, headers=admin).json()
    cambio = client.put(f"/api/admin/universidades/{nueva['id']}", json={**UNIVERSIDAD, "ciudad": "Potosí"}, headers=admin)
    assert cambio.status_code == 200 and cambio.json()["ciudad"] == "Potosí"
    assert client.delete(f"/api/admin/universidades/{nueva['id']}", headers=admin).status_code == 204
    assert client.put(f"/api/admin/universidades/{nueva['id']}", json=UNIVERSIDAD, headers=admin).status_code == 404


def test_datos_invalidos_dan_422_con_motivo(client, admin):
    r = client.post("/api/admin/universidades", json={**UNIVERSIDAD, "tipo": "inventada"}, headers=admin)
    assert r.status_code == 422 and "tipo" in r.json()["detail"]
    r = client.post("/api/admin/universidades", json={**UNIVERSIDAD, "sitio_web": "javascript:alert(1)"}, headers=admin)
    assert r.status_code == 422


def test_convocatoria_no_puede_cerrar_antes_de_abrir(client, admin):
    facultad = client.get("/api/admin/facultades", headers=admin).json()[0]
    r = client.post("/api/admin/convocatorias", headers=admin, json={
        "facultad_id": facultad["id"], "titulo": "Prueba", "modalidad_ingreso": "examen",
        "inscripcion_inicio": "2026-12-10", "inscripcion_fin": "2026-12-01",
    })
    assert r.status_code == 422 and "terminar antes" in r.json()["detail"]


def test_padre_inexistente_da_422(client, admin):
    r = client.post("/api/admin/facultades", json={"universidad_id": 9999, "nombre": "Facultad X", "area": "salud"}, headers=admin)
    assert r.status_code == 422


def test_no_se_borra_lo_que_tiene_hijos(client, admin):
    uni = client.get("/api/admin/universidades", headers=admin).json()[0]
    r = client.delete(f"/api/admin/universidades/{uni['id']}", headers=admin)
    assert r.status_code == 409 and "facultades" in r.json()["detail"]


def test_recurso_desconocido_da_404(client, admin):
    assert client.get("/api/admin/usuarios", headers=admin).status_code == 404


def test_el_cliente_no_puede_fijar_el_id(client, admin):
    r = client.post("/api/admin/universidades", json={**UNIVERSIDAD, "id": 1}, headers=admin)
    assert r.status_code == 201 and r.json()["id"] != 1


# ---------- mensajes de contacto ----------

def test_mensajes_se_ven_y_se_borran(client, admin):
    client.post("/api/contacto", json={"nombre": "Ana", "email": "ana@ejemplo.com", "mensaje": "Hola, ¿hay becas?"})
    lista = client.get("/api/admin/mensajes", headers=admin).json()
    assert lista[0]["nombre"] == "Ana"
    assert client.delete(f"/api/admin/mensajes/{lista[0]['id']}", headers=admin).status_code == 204
    assert client.get("/api/admin/mensajes", headers=admin).json() == []


# ---------- imágenes y videos ----------

def test_subir_imagen_y_video(client, admin, tmp_path):
    img = _subir(client, admin, PNG)
    assert img.status_code == 201
    datos = img.json()
    assert datos["tipo"] == "imagen" and datos["url"].startswith("/media/") and datos["url"].endswith(".png")
    assert (tmp_path / "subidas" / datos["archivo"]).is_file()

    vid = _subir(client, admin, MP4, "clip.mp4")
    assert vid.status_code == 201 and vid.json()["tipo"] == "video"
    assert len(client.get("/api/admin/media", headers=admin).json()) == 2


def test_el_tipo_se_decide_por_el_contenido_no_por_el_nombre(client, admin):
    html = b"<html><script>alert(1)</script></html>"
    assert _subir(client, admin, html, "inocente.png").status_code == 415
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    assert _subir(client, admin, svg, "logo.svg").status_code == 415
    assert _subir(client, admin, b"MZ\x90\x00programa", "foto.png").status_code == 415


def test_archivo_vacio_o_demasiado_grande(client, admin, monkeypatch):
    assert _subir(client, admin, b"").status_code == 422
    monkeypatch.setattr(medios, "LIMITE_IMAGEN", 50)
    assert _subir(client, admin, PNG).status_code == 413


def test_nombre_guardado_es_aleatorio_aunque_el_original_sea_malicioso(client, admin):
    r = _subir(client, admin, PNG, "../../etc/passwd.png")
    assert r.status_code == 201
    assert "/" not in r.json()["archivo"] and ".." not in r.json()["archivo"]


def test_subir_exige_ser_administrador(client):
    r = client.post("/api/admin/media", files={"archivo": ("foto.png", PNG, "image/png")})
    assert r.status_code == 401


def test_no_se_borra_un_archivo_en_uso(client, admin, tmp_path):
    media = _subir(client, admin, PNG).json()
    uni = client.post("/api/admin/universidades", json={**UNIVERSIDAD, "imagen_url": media["url"]}, headers=admin).json()
    assert client.delete(f"/api/admin/media/{media['id']}", headers=admin).status_code == 409

    client.put(f"/api/admin/universidades/{uni['id']}", json=UNIVERSIDAD, headers=admin)
    assert client.delete(f"/api/admin/media/{media['id']}", headers=admin).status_code == 204
    assert not (tmp_path / "subidas" / media["archivo"]).exists()


def test_imagen_de_universidad_solo_acepta_archivos_de_la_biblioteca(client, admin):
    r = client.post("/api/admin/universidades", json={**UNIVERSIDAD, "imagen_url": "https://malo.example/x.png"}, headers=admin)
    assert r.status_code == 422


# ---------- portada ----------

def test_portada_por_defecto_y_cambio(client, admin):
    assert client.get("/api/ajustes").json()["portada_titulo"]
    r = client.put("/api/admin/ajustes", json={"portada_titulo": "Nuevo título"}, headers=admin)
    assert r.status_code == 200
    assert client.get("/api/ajustes").json()["portada_titulo"] == "Nuevo título"


def test_portada_rechaza_claves_o_enlaces_raros(client, admin):
    assert client.put("/api/admin/ajustes", json={"otra_cosa": "x"}, headers=admin).status_code == 422
    assert client.put("/api/admin/ajustes", json={"portada_imagen": "https://malo.example/x.png"}, headers=admin).status_code == 422
    assert client.put("/api/admin/ajustes", json={"portada_titulo": "x" * 500}, headers=admin).status_code == 422


def test_cambiar_la_portada_exige_ser_administrador(client):
    assert client.put("/api/admin/ajustes", json={"portada_titulo": "hackeado"}).status_code == 401


# ---------- presentación pública de universidades e imagen de la convocatoria ----------

def test_la_universidad_guarda_descripcion_telefono_y_redes(client, admin):
    base = client.get("/api/admin/universidades", headers=admin).json()[0]
    base.pop("id")
    r = client.post("/api/admin/universidades", headers=admin, json={
        **base, "nombre": "Universidad con redes", "sigla": "UR",
        "descripcion": "Universidad de prueba para las redes.", "contacto": "4501512",
        "facebook": "https://facebook.com/ur", "instagram": "https://instagram.com/ur", "tiktok": "https://tiktok.com/@ur",
    })
    assert r.status_code == 201, r.text
    publica = next(u for u in client.get("/api/universidades").json() if u["sigla"] == "UR")
    assert publica["contacto"] == "4501512" and publica["tiktok"] == "https://tiktok.com/@ur"
    paquete = json.loads(client.get("/api/paquete").json()["datos"])
    assert any(u.get("instagram") == "https://instagram.com/ur" for u in paquete["universidades"])  # llega al celular


def test_las_redes_de_la_universidad_deben_ser_enlaces(client, admin):
    base = client.get("/api/admin/universidades", headers=admin).json()[0]
    base.pop("id")
    r = client.post("/api/admin/universidades", headers=admin, json={**base, "nombre": "Mala", "sigla": "M", "tiktok": "javascript:alert(1)"})
    assert r.status_code == 422


def test_la_facultad_lleva_la_imagen_de_su_convocatoria(client, admin):
    facultad = client.get("/api/admin/facultades", headers=admin).json()[0]
    facultad.pop("id")
    r = client.post("/api/admin/facultades", headers=admin, json={**facultad, "nombre": "Con afiche", "convocatoria_imagen_url": "/media/afiche.jpg"})
    assert r.status_code == 201, r.text
    nueva = next(f for f in client.get("/api/facultades").json() if f["nombre"] == "Con afiche")
    assert nueva["convocatoria_imagen_url"] == "/media/afiche.jpg"
    assert client.get(f"/api/facultades/{nueva['id']}").json()["convocatoria_imagen_url"] == "/media/afiche.jpg"
    mala = client.post("/api/admin/facultades", headers=admin, json={**facultad, "nombre": "Mala", "convocatoria_imagen_url": "https://otro.sitio/x.jpg"})
    assert mala.status_code == 422  # solo se aceptan imágenes subidas al panel


def test_no_se_borra_una_imagen_usada_por_una_facultad_ni_un_preuniversitario(client, admin):
    afiche = _subir(client, admin, PNG, "afiche.png").json()
    facultad = client.get("/api/admin/facultades", headers=admin).json()[0]
    facultad.pop("id")
    client.post("/api/admin/facultades", headers=admin, json={**facultad, "nombre": "Con afiche 2", "convocatoria_imagen_url": afiche["url"]})
    assert client.delete(f"/api/admin/media/{afiche['id']}", headers=admin).status_code == 409

    foto = _subir(client, admin, PNG, "foto.png").json()
    preu = client.get("/api/admin/preuniversitarios", headers=admin).json()[0]
    preu.pop("id")
    client.post("/api/admin/preuniversitarios", headers=admin, json={**preu, "nombre": "Con foto", "imagen_url": foto["url"]})
    assert client.delete(f"/api/admin/media/{foto['id']}", headers=admin).status_code == 409
