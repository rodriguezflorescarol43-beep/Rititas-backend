// Lo corre tests/test_paridad.py: ejecuta el motor del celular (JavaScript) con las mismas entradas
// que el servidor y devuelve los resultados para compararlos.
import { conEstado } from '../../frontend/src/datos/estado.js'
import { verificar } from '../../frontend/src/datos/firma.js'
import { evaluar, planes } from '../../frontend/src/datos/motor.js'

let entrada = ''
for await (const trozo of process.stdin) entrada += trozo
const { paquete, casos, hoy, firmado, clave, condiciones } = JSON.parse(entrada)

const resultados = casos.map((c) => evaluar(paquete, c, hoy))
const alterado = { ...firmado, datos: firmado.datos.replace('"costo_mensual_bs":50', '"costo_mensual_bs":5') }

console.log(
  JSON.stringify({
    resultados,
    convocatorias: paquete.convocatorias.map((c) => conEstado(c, hoy)),
    planes: planes(paquete, resultados[0], condiciones, hoy),
    firmaValida: await verificar(firmado, clave),
    firmaAlteradaValida: await verificar(alterado, clave),
  }),
)
