# Despega · Backend

**Abstracthon 2026.** «Despega» (guía de ingreso a la universidad) es una página web para quienes terminan el colegio en zonas alejadas (provincias) y no saben **qué
estudiar**, **qué preuniversitarios existen** ni **cuándo son las convocatorias**.

Este repositorio es el **backend**: la API, la base de datos y el panel de administración. La página que ve el
estudiante está en el repositorio del frontend. Más detalle: [informe técnico](docs/INFORME-TECNICO.docx) y
[correcciones aplicadas](docs/CORRECCIONES.md).

| Parte | Repositorio |
|---|---|
| **Backend** (este) | https://github.com/rodriguezflorescarol43-beep/Rititas-backend |
| **Frontend** (la página, PWA) | https://github.com/rodriguezflorescarol43-beep/Rititas-frondend |

## El problema y la solución

**Problema.** Quien sale del colegio en una provincia suele no saber qué estudiar, no conoce los preuniversitarios
(institutos) ni las fechas de ingreso, que están dispersas en PDFs de cada universidad, y además tiene señal débil
o intermitente.

**Solución.** Una guía web (PWA) con **Universidades** (públicas y privadas; dentro de cada una, sus facultades y la
**convocatoria** de cada facultad), **Preuniversitario (institutos)** y **¿No sabes qué estudiar?** (test con carreras
recomendadas **con el motivo explicado** y planes A, B y C). Funciona con señal débil y sin señal, sin registro.
Cada dato muestra su **fuente y su fecha de verificación**.

> **Alcance actual: solo Cochabamba.** Es una versión de prueba con datos reales de la UMSS, UCB, UPB, Univalle y cuatro
> preuniversitarios. Lo que las fuentes no publican (por ejemplo, costos mensuales) **no se inventa**: queda vacío.

## Qué incluye el backend

- **API REST** (FastAPI) con el catálogo: universidades, facultades, carreras, convocatorias, preuniversitarios,
  embajadores y el test vocacional.
- **Paquete de datos firmado** (`/api/paquete`): todo el catálogo en **una sola respuesta (~31 KB)**, con firma
  digital, `ETag` y compresión, pensado para señal débil.
- **Panel de administración** (`/admin` en la página): edita todo, sube imágenes y videos, cambia la portada.
- **IA solo para el administrador:** **Importar con IA** (un modelo de lenguaje lee un PDF o una foto y propone datos
  con su cita), un **verificador de citas** que detecta datos inventados, **Medir la IA** y el Detective de datos.
  **Ninguna IA toca la parte pública.**
- **130 pruebas automáticas.**

## Tecnología y capas

FastAPI · SQLModel · SQLite · Pydantic · `cryptography` (firma ECDSA P-256) · `pypdf` · pytest.

```text
backend/app/
  api/            Capa de API: rutas HTTP (sin lógica de negocio)
  services/       Capa de negocio: convocatorias, test, paquete, Detective, propuestas, verificador, lector con IA, medición
  repositories/   Capa de datos: consultas a SQLite
  models/         Capa de dominio: tablas
  schemas/        Contratos de entrada y salida
  core/           Configuración, base de datos, seguridad, firma y migración automática
  seed.py         Datos de EJEMPLO
backend/tools/    medir.py, extractor_reglas.py (sin IA) y cargar_cochabamba.py (datos reales de Cochabamba)
tests/            130 pruebas
docs/             Formato de las propuestas, informe técnico (Word) y resumen de correcciones
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
git clone https://github.com/rodriguezflorescarol43-beep/Rititas-frondend.git frontend
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
| `GEMINI_API_KEY` | Clave de Google AI Studio para el botón **«Leer con IA»**. Sin ella el botón no aparece y se usa Claude a mano | Sin definir |
| `GEMINI_MODELO` | Modelo principal de Gemini (Google cambia los nombres seguido) | `gemini-3.1-flash-lite` |
| `GEMINI_RESPALDOS` | Modelos que se prueban, en orden, si el principal no existe o está saturado | `gemini-flash-lite-latest,gemini-3.5-flash,gemini-3.8-flash` |

Para publicar, define siempre `GUIA_ADMIN_PASSWORD` y usa **HTTPS**. **Nunca subas una clave ni una contraseña a Git**:
se definen solo como variables de entorno en el servidor. Si usas una contraseña fija de demostración, **cámbiala por
una privada** al terminar.

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
preuniversitarios, **imágenes y videos**, la **portada** y los mensajes de contacto.

- **Seguridad:** token firmado que vence a las 8 horas, máximo 5 intentos fallidos por minuto, validación de todos los
  datos, nombres de archivo aleatorios.
- **Imágenes y videos:** PNG, JPG, WEBP o GIF hasta 5 MB; MP4 o WEBM hasta 40 MB. El formato se decide por el
  **contenido** del archivo, no por su nombre, y no se aceptan SVG ni HTML.
- **Embajadores:** ya no se administran desde el panel. Si se vuelven a usar, solo se publican con **mayoría de edad**,
  **consentimiento** y su fecha.
- **Presentación pública:** cada universidad lleva una descripción corta, teléfono y redes (Facebook, Instagram,
  TikTok); cada facultad puede llevar la **imagen de su convocatoria**. Solo se muestra lo que se carga: nunca se
  inventa un enlace.
- **Migración automática:** si se agregan columnas nuevas a una tabla, se suman solas sin perder datos.

## IA solo para el administrador

La IA **no habla con los estudiantes**. Mensaje en una frase: *«la IA propone, el verificador comprueba cada frase,
una persona aprueba, y los datos de los estudiantes nunca llegan a la IA»*.

| Herramienta | Qué hace | ¿Usa IA? |
|---|---|---|
| **Importar con IA → «Leer con IA»** | El administrador sube un PDF o una foto; **Gemini** propone los datos con la frase exacta donde los leyó. No guarda nada | **Sí** (Gemini) |
| **Verificador de citas** | Comprueba que cada frase exista en el documento y que el valor coincida con su frase. Semáforo verde, amarillo o rojo | No: reglas |
| **Medir la IA** | Con el documento a la vista, la persona marca cada dato; calcula aciertos, datos inventados, errores atrapados por el verificador y los compara con un método sin IA | No: cuentas |
| **Qué revisar hoy** (el Detective) | Avisa qué mirar primero: convocatorias sin verificar que cierran pronto, fechas raras, costos fuera de lo normal, posibles duplicados | No: reglas y estadística |
| **Claude a mano / skill `/actualizar-datos`** | Alternativa sin clave: Claude lee el documento y prepara la propuesta, que se pega en el panel | **Sí** (Claude) |
| **`backend.tools.medir` y `extractor_reglas`** | Medición y extractor por reglas, desde la terminal | No |

### Cómo funciona «Leer con IA»

1. En el panel: **Importar con IA → Elegir PDF o foto → Leer con IA** (unos 3 segundos).
2. El servidor envía el documento y la lista de universidades y facultades a Gemini con la orden de **no inventar y
   citar la frase exacta**. Sale una **propuesta**, no un cambio.
3. Si el documento es un PDF con texto, ese texto alimenta el **verificador de citas**. Cada dato queda en 🟢 (la frase
   existe y el valor coincide), 🟡 (revísalo) o 🔴 (la frase no aparece: posible invento).
4. La persona marca lo que aprueba y publica. El historial guarda la fuente y la frase de cada dato.

La respuesta de la IA **se limpia antes de mostrarse**: si trae un detalle mal (por ejemplo un tipo de dato no
permitido), se descarta solo ese cambio y se avisa. Si un modelo está saturado, se prueba otro automáticamente.

**Sin internet o sin clave:** el botón **«Probar con un documento de ejemplo»** carga una respuesta guardada sobre un
documento ficticio, con un error a propósito para ver el semáforo. **No se puede publicar.**

### Seguridad y límites de diseño

- La IA **no tiene permisos de escritura**: solo entrega una propuesta. El servidor **vuelve a validar todo** antes de guardar.
- La **clave de Gemini vive solo en el servidor**: no se envía al navegador ni se guarda en la base de datos.
- Las rutas `/api/admin/ia/*` exigen sesión de administrador.
- **No se pueden** crear ni cambiar embajadores ni mensajes (datos personales) por esta vía.
- El contenido de un documento se trata como **datos, no como instrucciones**.
- Al aprobar, el registro queda con **la fecha de hoy como verificación** y la fuente es siempre **el nombre real del archivo**.
- **Privacidad:** con el nivel gratis de Google, lo que se envía puede usarse para mejorar sus productos. Sube **solo
  documentos públicos**, nunca los mensajes de estudiantes.
- Si usas Claude Code para la alternativa manual, **no definas `ANTHROPIC_API_KEY`**: haría que te cobre por API en vez de usar tu plan.

El formato de las propuestas y un ejemplo están en [docs/FORMATO_PROPUESTA.md](docs/FORMATO_PROPUESTA.md).

> **Qué NO está medido todavía:** cuánto acierta la IA con documentos reales a gran escala. «Medir la IA» existe para
> hacerlo: mide varios documentos reales y publica **tus** cifras.

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
| `GET /api/admin/ia/estado` · `POST /api/admin/ia/leer` · `GET /api/admin/ia/ejemplo` | «Leer con IA»: estado, lectura de un PDF o foto y documento de ejemplo |
| `POST /api/admin/propuestas/analizar` · `POST /api/admin/propuestas/aplicar` | Revisa una propuesta sin guardar (con verificador de citas) y aplica solo lo aprobado |
| `GET/POST /api/admin/mediciones` | Medición de la IA y su resultado acumulado |

## Pruebas

```powershell
pytest
```

130 pruebas: reglas del test, API, panel y seguridad, paquete firmado, migración, Detective, importación de propuestas,
verificador de citas, medición de la IA y lector con IA (Gemini se simula: las pruebas no usan internet ni gastan cuota).

La prueba de **paridad** (`tests/test_paridad.py`) compara el motor del teléfono (JavaScript, en el repositorio del
frontend) con el del servidor en más de 40 casos. Para correrla hay que clonar el frontend en `./frontend`; si no está,
**se omite** y las demás pasan igual. También necesita Node.

## Cargar datos reales

Hay dos formas de tener datos:

- **Datos de ejemplo** (`python -m backend.app.seed`): universidades «Ejemplo», inventadas, para probar.
- **Datos reales de Cochabamba** (`python -m backend.tools.cargar_cochabamba`): carga la UMSS, UCB, UPB y Univalle con sus
  facultades y carreras, y cuatro preuniversitarios, tomados de sus sitios oficiales. **Hace una copia de respaldo** de
  la base y **reemplaza** el catálogo. Lo que no se encontró (costos, fechas 2027) queda vacío.

Para completar o corregir:
1. Entra al panel y edita los registros, o usa **Importar con IA**.
2. En cada registro llena `fuente_url` (enlace oficial) y `verificado_en` (`AAAA-MM-DD`).

Mientras `verificado_en` esté vacío, la página muestra «Tomado de la fuente · falta confirmar» (o «Dato de ejemplo ·
sin verificar» si no hay fuente). **No publiques fechas que no hayas confirmado en la fuente oficial.**

## Límites de la versión 1

- **Solo Cochabamba.** Los datos son reales pero **faltan por confirmar** (`verificado_en` vacío) y no hay costos mensuales
  ni fechas 2027 de la mayoría de universidades.
- **SQLite:** basta para un MVP con pocos administradores. Si crece, el siguiente paso es PostgreSQL (SQLModel facilita el cambio).
- **La IA puede equivocarse:** por eso hay verificador y aprobación humana. Con una **foto** el verificador no puede
  comprobar las frases (no hay texto) y el semáforo queda en amarillo.
- **Gemini gratis** tiene límites por minuto y por día, y a veces los modelos grandes están saturados (se prueban otros).
- **Un solo administrador:** no hay cuentas ni roles, y no se guarda quién cambió qué (el historial anota qué y de dónde).
- **No se probó** en un teléfono real ni con red lenta simulada.
- **Solo español.**
- El test orienta, **no diagnostica**; así lo dice la propia página.

