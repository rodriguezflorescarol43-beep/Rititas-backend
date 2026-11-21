# Guía de ingreso · Backend

**Abstracthon 2026.** Página web para quienes terminan el colegio en zonas alejadas (provincias) y no saben **qué
estudiar**, **qué preuniversitarios existen** ni **cuándo son las convocatorias**.

Este repositorio es el **backend**: la API, la base de datos y el panel de administración. La página que ve el
estudiante está en el repositorio del frontend.

| Parte | Repositorio |
|---|---|
| **Backend** (este) | https://github.com/rodriguezflorescarol43-beep/backend-hackaton |
| **Frontend** (la página, PWA) | https://github.com/rodriguezflorescarol43-beep/hackaton2026-oficial |

## El problema y la solución

**Problema.** Quien sale del colegio en una provincia suele no saber qué estudiar, no conoce los preuniversitarios
(institutos) ni las fechas de ingreso, que están dispersas en PDFs de cada universidad, y además tiene señal débil
o intermitente.

**Solución.** Una guía web (PWA) con: **Convocatorias** por facultad, **Preuniversitario (institutos)**,
**Universidades** (públicas, privadas y técnicas) y **¿No sabes qué estudiar?** (test con carreras recomendadas **con
el motivo explicado**, plan A/B/C y costo estimado del primer año). Funciona con señal débil y sin señal, sin registro.
Cada dato muestra su **fuente y su fecha de verificación**.

## Qué incluye el backend

- **API REST** (FastAPI) con el catálogo: universidades, facultades, carreras, convocatorias, preuniversitarios,
  embajadores y el test vocacional.
- **Paquete de datos firmado** (`/api/paquete`): todo el catálogo en **una sola respuesta de ~17 KB**, con firma
  digital, `ETag` y compresión, pensado para señal débil.
- **Panel de administración** (`/admin` en la página): edita todo, sube imágenes y videos, cambia la portada.
- **IA solo para el administrador:** el Detective de datos, la importación de propuestas con cita de la fuente y una
  skill de Claude Code. **Ninguna IA toca la parte pública.**
- **95 pruebas automáticas.**

## Tecnología y capas

FastAPI · SQLModel · SQLite · Pydantic · `cryptography` (firma ECDSA P-256) · `pypdf` · pytest.

```text
backend/app/
  api/            Capa de API: rutas HTTP (sin lógica de negocio)
  services/       Capa de negocio: estado de convocatorias, motor del test, paquete, Detective, propuestas
  repositories/   Capa de datos: consultas a SQLite
  models/         Capa de dominio: tablas
  schemas/        Contratos de entrada y salida
  core/           Configuración, base de datos, seguridad, firma y migración automática
  seed.py         Datos de EJEMPLO
backend/tools/    medir.py y extractor_reglas.py (medición y extractor sin IA)
tests/            95 pruebas
docs/             Formato de las propuestas de IA y un ejemplo
.claude/skills/   Skill /actualizar-datos para Claude Code
```

Regla de las capas: `api → services → repositories → models`. Una capa solo llama a la de abajo.

## Cómo correrlo

Necesitas **Python 3.10+** (y Node 20+ solo si vas a compilar el frontend).

### Solo la API

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m backend.app.seed                 # datos de ejemplo (--reset los recarga)
uvicorn backend.app.main:app --port 8000
```

La documentación interactiva queda en http://localhost:8000/docs.

### Con la página (frontend) en el mismo servidor

Clona el frontend **dentro** de esta carpeta con el nombre `frontend` y compílalo una vez:

```powershell
git clone https://github.com/rodriguezflorescarol43-beep/hackaton2026-oficial.git frontend
cd frontend
npm install
npm run build
cd ..
uvicorn backend.app.main:app --port 8000
```

Abre http://localhost:8000/ : FastAPI entrega la API en `/api` y la página compilada en `/`. La carpeta `frontend/`
no se sube a este repositorio (está en `.gitignore`).

## Variables de entorno

| Variable | Para qué sirve | Por defecto |
|---|---|---|
| `GUIA_ADMIN_PASSWORD` | Contraseña del panel de administración | Si no se define, se genera una temporal y se **muestra en la consola** al arrancar |
| `GUIA_SECRET` | Secreto para firmar los tokens del panel | Aleatorio en cada arranque |
| `GUIA_CLAVE_FIRMA` | Clave privada (PEM) para firmar el paquete de datos | Se crea sola en `backend/clave_firma.pem` (**no se sube a Git**) |
| `GUIA_DB` | URL de la base de datos | `sqlite:///backend/guia.db` |
| `GUIA_UPLOADS` | Carpeta de imágenes y videos subidos | `backend/uploads/` |
| `GUIA_DIST` | Carpeta del frontend compilado | `frontend/dist` |

Para publicar, define siempre `GUIA_ADMIN_PASSWORD` y usa **HTTPS**.

## Pensada para señal débil (lado del servidor)

| Problema | Qué hace el backend |
|---|---|
| Peso | Compresión gzip de las respuestas de texto |
| Latencia | **Un solo archivo** (`/api/paquete`) con todo el catálogo, para que el teléfono haga una petición y trabaje sin red |
| Cortes | `ETag`: si los datos no cambiaron responde **304 sin cuerpo**. Los envíos del teléfono se reintentan solos |
| Datos viejos | Las convocatorias viajan con sus **fechas**; el estado («abierta», «cierra en 12 días») lo calcula el teléfono con la fecha de hoy |

### Paquete firmado
`/api/paquete` va **firmado con ECDSA P-256**. Una persona puede pasar el archivo a otra por WhatsApp y la página
comprueba el sello: rechaza cualquier archivo alterado o más viejo que lo que ya tiene. La clave pública está en
`/api/paquete/clave`. Comprobar el sello exige **HTTPS** (o `localhost`).

## Panel de administración

Una sola contraseña, sin cuentas. Permite administrar universidades, facultades, carreras, convocatorias,
preuniversitarios, **embajadores**, **imágenes y videos**, la **portada** y los mensajes de contacto.

- **Seguridad:** token firmado que vence a las 8 horas, máximo 5 intentos fallidos por minuto, validación de todos los
  datos, nombres de archivo aleatorios.
- **Imágenes y videos:** PNG, JPG, WEBP o GIF hasta 5 MB; MP4 o WEBM hasta 40 MB. El formato se decide por el
  **contenido** del archivo, no por su nombre, y no se aceptan SVG ni HTML.
- **Embajadores:** solo se publican si son **mayores de 18 años**, dieron su **consentimiento** y consta la fecha.
- **Migración automática:** si se agregan columnas nuevas a una tabla, se suman solas sin perder datos.

## IA solo para el administrador

La IA **no habla con los estudiantes**. Mensaje en una frase: *«la IA propone, una persona verifica, y los datos de los
estudiantes nunca salen del servidor»*.

| Herramienta | Qué hace | ¿Usa IA? |
|---|---|---|
| **Qué revisar hoy** (el Detective) | Avisa qué mirar primero: convocatorias sin verificar que cierran pronto, fechas raras, costos fuera de lo normal (comparados con la mediana), posibles duplicados | **No**: reglas y estadística simple |
| **Importar propuesta** | Recibe un archivo con datos sugeridos y **la cita de la fuente** de cada uno. Muestra el antes y el después; solo se guarda lo que la persona aprueba, campo por campo. Queda un historial | No: es la pantalla de revisión |
| **Skill `/actualizar-datos`** | Con Claude Code, lee un **PDF o la foto de un afiche** y prepara ese archivo | **Sí** (Claude) |
| **`backend.tools.medir`** | Cuenta cuántos datos acertó, falló, no encontró e inventó una propuesta frente a lo que anotaste a mano | No |
| **`backend.tools.extractor_reglas`** | Lee un PDF o texto con reglas (sin IA): punto de comparación y plan B gratis | No |

**Cómo se usa** (con un plan Claude Pro, sin clave de API):
1. En el panel: **Importar propuesta → Descargar referencias**.
2. Abre Claude Code **dentro de esta carpeta** y escribe `/actualizar-datos propuestas/afiche.jpg` (o un PDF).
3. Claude guarda `propuestas/AAAA-MM-DD-….json`.
4. En el panel: **Importar propuesta → elige el archivo → revisa → marca lo que apruebes → Aplicar**.

El formato y un ejemplo están en [docs/FORMATO_PROPUESTA.md](docs/FORMATO_PROPUESTA.md).

**Seguridad y límites de diseño**
- La IA **no tiene permisos de escritura**: solo entrega un archivo. El servidor **vuelve a validar todo** antes de guardar.
- **No se pueden** crear ni cambiar embajadores ni mensajes (datos personales) por esta vía.
- El contenido de un documento se trata como **datos, no como instrucciones**.
- Al aprobar, el registro queda con **la fecha de hoy como verificación** y, si la fuente es un enlace, con ese enlace.
- **No definas la variable `ANTHROPIC_API_KEY`**: haría que Claude Code te cobre por API en vez de usar tu plan.
- Sube a Claude **solo documentos públicos**, nunca los mensajes de estudiantes.

> **Qué NO está medido todavía:** cuánto acierta Claude leyendo documentos reales. La herramienta `medir` existe para
> hacerlo: anota a mano 5 a 10 documentos, compara «solo reglas» contra «Claude» y publica **tus** cifras.

## Endpoints principales

| Ruta | Descripción |
|---|---|
| `GET /api/meta` | Departamentos, áreas y tipos de facultad |
| `GET /api/universidades?tipo=&departamento=` | Universidades |
| `GET /api/facultades?universidad_id=` | Facultades con estado de convocatoria |
| `GET /api/facultades/{id}` | Facultad con carreras y convocatorias |
| `GET /api/convocatorias?estado=abierta` | Convocatorias (`abierta`, `proxima`, `cerrada`) |
| `GET /api/preuniversitarios?departamento=` · `/{id}` | Preuniversitarios y su perfil |
| `GET /api/embajadores` | Embajadores publicados (con consentimiento) |
| `GET /api/orientacion/preguntas` · `POST /api/orientacion/resultado` | Test y carreras recomendadas |
| `GET /api/paquete` · `GET /api/paquete/clave` | Catálogo firmado y su clave pública |
| `POST /api/contacto` | Guarda un mensaje |
| `/api/admin/*` | Panel (requiere sesión): CRUD, medios, portada, revisión, propuestas, historial |

## Pruebas

```powershell
pytest
```

95 pruebas: reglas del test, API, panel y seguridad, paquete firmado, migración, Detective e importación de
propuestas, herramientas de medición.

La prueba de **paridad** (`tests/test_paridad.py`) compara el motor del teléfono (JavaScript, en el repositorio del
frontend) con el del servidor en más de 40 casos. Para correrla hay que clonar el frontend en `./frontend`; si no está,
**se omite** y las demás pasan igual. También necesita Node.

## Cargar datos reales

Los datos incluidos son **inventados** (universidades «Ejemplo»). Para publicar datos reales:

1. Entra al panel y borra o edita los registros de ejemplo, o crea los tuyos.
2. En cada registro llena `fuente_url` (enlace oficial) y `verificado_en` (`AAAA-MM-DD`).
3. O usa **Importar propuesta** con la skill de IA.

Mientras `verificado_en` esté vacío, la página muestra «Dato de ejemplo · sin verificar».
**No publiques fechas que no hayas confirmado en la fuente oficial.**

## Límites de la versión 1

- **Los datos son de ejemplo.** Falta cargar y verificar los reales.
- **Costos:** el costo por universidad es uno solo (no por carrera). Las estimaciones del primer año son aproximadas.
- **Un solo administrador:** no hay cuentas ni roles, y no se guarda quién cambió qué (el historial anota qué y de dónde).
- **No se probó** en un teléfono real ni con red lenta simulada.
- **Solo español.**
- El test orienta, **no diagnostica**; así lo dice la propia página.
