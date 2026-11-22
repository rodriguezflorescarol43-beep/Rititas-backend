# Formato de una propuesta

Una **propuesta** es un archivo JSON con datos sugeridos por una IA (o por una persona) para el panel de
administración. El panel la revisa **sin guardar nada**, muestra el antes y el después con la cita de la fuente, y
solo aplica lo que el administrador aprueba. Cualquier IA puede generarla mientras respete este formato.

## Estructura

```json
{
  "formato": 1,
  "origen": "Claude (actualizar-datos)",
  "fuente": "https://universidad.edu.bo/convocatoria.pdf",
  "cambios": [ { ...un cambio... } ]
}
```

| Campo | Obligatorio | Qué es |
|---|---|---|
| `formato` | Sí | Siempre `1` |
| `origen` | No | Quién la generó (se guarda en el historial) |
| `fuente` | No | **Enlace `https`** de donde salen los datos, o el **nombre del archivo** (por ejemplo `afiche.jpg`) |
| `cambios` | Sí | De 1 a 50 cambios |
| `texto_fuente` | No (muy recomendado) | El texto del documento oficial. El panel lo agrega solo cuando el administrador lo pega: con él se **verifica que cada cita exista** en el documento y que el valor coincida con su cita (semáforo verde, amarillo o rojo) |

## Un cambio

| Campo | Obligatorio | Qué es |
|---|---|---|
| `accion` | Sí | `crear` o `actualizar` |
| `recurso` | Sí | `universidades`, `facultades`, `carreras`, `convocatorias` o `preuniversitarios` |
| `id` | Solo al actualizar | Número del registro (sale de «Descargar referencias») |
| `datos` | Sí | Los campos a crear o cambiar. Al actualizar, solo los que cambian |
| `referencias` | No | Para crear: el padre por nombre, `{"universidad": "UPE", "facultad": "Facultad de Ingeniería"}` |
| `evidencia` | Muy recomendado | Para cada campo, la **frase textual** del documento donde se leyó |
| `confianza` | No | `alta`, `media` o `baja` |

> **No se pueden** crear ni cambiar embajadores ni mensajes: tienen datos personales.

## Campos por tipo

- **universidades:** `nombre`, `sigla`, `tipo` (`publica`, `privada`, `tecnico`), `ciudad`, `departamento`,
  `sitio_web`, `costo_mensual_bs`, `becas`, `descripcion` (una frase corta), `contacto` (teléfono o número de
  informaciones), `facebook`, `instagram`, `tiktok` (enlaces `https`).
- **facultades:** `nombre`, `area` (`salud`, `tecnologia`, `negocios`, `social`, `arte`, `naturaleza`) y la
  universidad (`universidad_id` o `referencias.universidad`).
- **carreras:** `nombre`, `area`, `duracion_anios` (1 a 10), `descripcion` y la facultad
  (`facultad_id` o `referencias.facultad`).
- **convocatorias:** `titulo`, `inscripcion_inicio`, `inscripcion_fin`, `fecha_examen`, `modalidad_ingreso`
  (`examen`, `preuniversitario`, `ambos`), `costo_inscripcion_bs`, `requisitos` y la facultad.
- **preuniversitarios:** `nombre`, `tipo` (`instituto`, `universidad`), `ciudad`, `departamento`, `duracion_meses`,
  `costo_bs`, `modalidad` (`presencial`, `virtual`, `mixta`), `prepara_para`, `contacto`, `zona`, `descripcion`,
  `direccion`, `referencia`, `latitud`, `longitud`, `whatsapp` (solo dígitos con código de país), `facebook`,
  `instagram`, `tiktok` (enlaces `https`), `materias` (separadas por coma) y `facultades_tipos`
  (`ciencias_tecnologia`, `medicina`, `economicas`, `juridicas`, `arquitectura`, `odontologia`, `humanidades`,
  `bioquimica`, separadas por coma).

Las fechas van en `AAAA-MM-DD` y los montos son números.

## Qué hace el panel con la propuesta

1. **Analiza** (no guarda): valida con las mismas reglas de siempre y avisa de errores y advertencias:
   campos desconocidos, datos **sin cita**, registros que ya existen, fechas que ya pasaron.
2. **Muestra** el antes y el después de cada campo, con la cita.
3. **Aplica solo lo aprobado**, campo por campo al actualizar. Vuelve a validar todo en el servidor.
4. Al aplicar, el registro queda con **la fecha de hoy como verificación** y, si la `fuente` es un enlace, con ese
   enlace. Todo queda en el **historial**: qué cambió, de qué fuente y con qué cita.
5. La página de los celulares se actualiza sola con el paquete nuevo.

## Medir qué tan bien lo hace una IA

```powershell
python -m backend.tools.medir propuesta.json verdad.json
```

`verdad.json` es una propuesta con lo que **tú** anotaste a mano del mismo documento. La herramienta cuenta, por campo,
cuántos datos acertó, cuántos se equivocó, cuántos no encontró y cuántos inventó. Sirve para comparar métodos con
documentos reales.

Para tener un punto de comparación **sin IA**:

```powershell
python -m backend.tools.extractor_reglas convocatoria.pdf --universidad UPE --facultad "Facultad de Ingeniería" --salida propuestas/reglas.json
```
