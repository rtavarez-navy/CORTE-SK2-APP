# Plan de diseño · la hoja de cada láser como hoja de cálculo

Complemento de `docs/PLAN_VISUAL.md`. Ese plan define colores, tipografía y layout general. Este define una sola pieza: el reporte de cada láser, que hoy no se ve ni se usa como la hoja de Google Sheets que reemplaza.

## 1. Por qué la app actual no quedó como una hoja de cálculo

Revisé `web/app.py` (función `laser_report`, `report_row`) y `web/style.css`. Las causas son estructurales, no de color:

1. **Es una tabla HTML con formularios dentro, no una cuadrícula.** Cada fila lleva un `<details>` "Corregir" y otro "Eliminar", que abren un formulario completo. Para cambiar un número hay que abrir un panel, escribir, guardar y recargar la página. Una hoja de cálculo permite escribir directo en la celda.
2. **Nada permite moverse como en una hoja.** No hay navegación con flechas, Tab o Enter entre celdas, ni selección de celda. Hoy no es posible saber en qué celda estás.
3. **No tiene encabezados de columna letra ni números de fila.** Una hoja muestra A, B, C… y 1, 2, 3…. Sin eso no se lee como hoja, y no se puede decir "la celda C12".
4. **Los campos calculados se ven igual que los capturados.** En el sheet, *Orden + Línea*, *Repeticiones*, *Dup.* y *Reprint* son fórmulas. En la app son texto normal, sin nada que indique que se calculan.
5. **La captura está encima de la tabla, en una tarjeta aparte.** En el sheet, la nueva fila es la última de la hoja, lista para escribir. Aquí el formulario ocupa la pantalla antes de la tabla.
6. **Los encabezados se parten en varias líneas y la tabla tiene 13 columnas con `min-width: 480px`.** Los textos largos ("Estado y acciones", "CPA (Supervisor)") se envuelven y la tabla se ve como un listado.
7. **No hay barra de fórmulas, ni pestañas de hoja, ni fila de totales.** El sheet tiene las tres cosas. Los totales están en un texto encima de la tabla.
8. **La cabecera de la tabla no se queda fija.** Al bajar, se pierden los nombres de las columnas.
9. **La Content-Security-Policy bloquea JavaScript.** `web/app.py` define `default-src 'none'; style-src 'self'`, sin `script-src`. Cualquier interacción con teclado (flechas, Enter para guardar, celda seleccionada) necesita un script externo. Hay que permitirlo explícitamente, sin `unsafe-inline`.
10. **El plan visual anterior no lo cubría.** `docs/PLAN_VISUAL.md` describía la tabla como "las mismas columnas" y no especificaba cómo se edita una celda. Esa falta es la que dejó la app sin el comportamiento de hoja.

## 2. Qué debe parecer y comportarse como hoja

Objetivo concreto: quien conoce el sheet entra a la app y puede trabajar sin capacitación. Mismas columnas, mismo orden, misma idea de nueva fila al final, y las mismas reglas visibles.

### Anatomía de la hoja

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Láser 4 · Turno 1 · 18/11/2026                    12,480 piezas confirmadas │
├───────┬────────────────────────────────────────────────────────────────────┤
│ B12   │ fx  =SIN_SO(B12)&"-"&C12                                          │  ← barra de fórmulas
├───────┼──────┬────────────┬───────┬──────────┬──────────┬────────┬────────┤
│       │  A   │     B      │   C   │    D     │    E     │   F    │   G    │  ← letras de columna
├───────┼──────┼────────────┼───────┼──────────┼──────────┼────────┼────────┤
│ fijo  │FECHA │ # DE ORDEN │ LINEA │# PIEZAS  │COMENTAR. │REPRINT │Orden+… │  ← encabezados (fijos)
├───────┼──────┼────────────┼───────┼──────────┼──────────┼────────┼────────┤
│   1   │18/11 │   4471     │   B   │   120    │          │        │4471-B  │
│   2   │18/11 │   4472     │   A   │    80    │ reprint  │   *    │4472-A  │
│   3   │18/11 │  [4473  ]  │ [ A ] │  [ 60 ]  │ [     ]  │        │        │  ← celda seleccionada
│   4   │      │            │       │          │          │        │        │  ← fila nueva
├───────┴──────┴────────────┴───────┴──────────┴──────────┴────────┴────────┤
│ Total                                                  12,480               │  ← fila de totales
├─────────────────────────────────────────────────────────────────────────────┤
│ [Turno 1 · Láser 4] [Turno 1 · Láser 5] …       Guardado · 14:26          │  ← pestañas y estado
└─────────────────────────────────────────────────────────────────────────────┘
```

### Columnas

Orden y nombres idénticos al sheet. Las columnas de la app que no existen en el sheet van al final, marcadas como "de la app".

| Letra | Columna | Tipo | Editable | Notas |
|---|---|---|---|---|
| A | FECHA | dato | sí (solo fila nueva) | Fecha de producción |
| B | # DE ORDEN | dato | sí | Solo dígitos |
| C | LINEA | dato | sí | Mayúsculas |
| D | # PIEZAS | dato | sí | Número entero positivo, alineado a la derecha |
| E | COMENTARIOS | dato | sí | Hasta 300 caracteres |
| F | * REPRINT * | fórmula | no | `*` si la clave está en Personal → Reprints |
| G | Orden + Línea | fórmula | no | Número sin prefijo SO-, guion, línea en mayúsculas |
| H | REPETICIONES | fórmula | no | Conteo de la clave en el mismo láser y turno |
| I | SKU | dato | sí | Captura manual |
| J | CPA (SUPERVISOR) | pendiente | no | Muestra "—" hasta la integración con CPA (Fase 6) |
| K | DUP. | fórmula | no | Conteo en toda la producción de la app |
| L | Operario | de la app | no | Nombre del operario que registró |
| M | Estado | de la app | no | Confirmado, Por revisar o Descartado |

Las columnas F, G, H, J y K llevan fondo `#101A14` y texto `#8FA196`. Son lo que en una hoja sería una fórmula: se distinguen a simple vista de lo que se escribe.

### Barra de fórmulas

Al seleccionar una celda, la barra superior muestra:

- A la izquierda, la referencia de la celda (por ejemplo `B12`).
- A la derecha, el contenido. En una celda de dato, el valor. En una celda calculada, la fórmula en texto, por ejemplo `=SIN_SO(B12)&"-"&C12`. Es la pista que hace que la columna se lea como hoja.

### Fila nueva

Siempre hay una fila vacía al final, como en el sheet. Escribir en ella y pulsar Enter crea el registro y deja una fila nueva abajo. La fila nueva no aparece con formulario encima; es la última fila de la cuadrícula.

Para el supervisor, la fila nueva pide el operario en la columna L antes de guardar. Para el operario, L es automática.

### Fila de totales

Al pie, una fila fija que muestra `=SUMA(D:D)` en la columna D, con el total de confirmados. Las filas pendientes o descartadas no suman.

### Pestañas de hoja

En la parte inferior, una pestaña por láser y turno del día, igual que las pestañas de un libro. Así un supervisor cambia de láser como cambia de hoja. El operario ve solo su pestaña.

### Estado de guardado

En la barra inferior, un texto que cambia según el estado de la última acción: "Guardando…", "Guardado · 14:26" o "No se guardó: la orden ya existe en este láser hoy. Revisa en Notificaciones." La acción y el mensaje usan los mismos verbos que el resto de la app.

## 3. Interacción con teclado (la parte que hace que parezca hoja)

| Tecla | Acción |
|---|---|
| Flechas | Mover la selección una celda |
| Tab / Shift+Tab | Siguiente / anterior celda de la fila; al final de la fila, pasa a la siguiente fila |
| Enter | Guardar la fila y bajar a la misma columna de la fila siguiente |
| Escape | Cancelar el cambio en la celda actual |
| Doble clic o F2 | Entrar a editar la celda |
| Ctrl+Z | Deshacer el último cambio de la sesión |
| Ctrl+C / Ctrl+V | Copiar y pegar un valor de celda |
| Inicio / Fin | Primera o última celda de la fila |

Pegar desde una hoja de cálculo de Google Sheets (texto separado por tabulaciones) crea varias filas. Eso ahorra captura y permite migrar un día del sheet en un solo paso.

Las celdas bloqueadas (filas de otro operario, columnas calculadas) se pueden seleccionar para leer la fórmula o el valor, pero no escribir. Al intentar escribir, la barra de estado dice "Esta celda no se puede editar" en lugar de no responder.

## 4. Permisos visibles

- **Operario:** ve todas las filas de su láser y turno. Puede editar solo sus filas. Las demás aparecen en tono apagado (`#516359` sobre fondo de hoja) sin cursor de edición.
- **Supervisor:** todas las filas editables, con la columna L visible y editable.
- **Desarrollador:** igual que supervisor, con acceso a historial de cambios desde el menú de fila.

## 5. Diseño visual de la cuadrícula

Ajusta el plan visual (`docs/PLAN_VISUAL.md`) a una tabla de hoja:

- **Modo oscuro** en estación y resumen; **modo claro** en reporte, según el plan visual.
- Líneas de cuadrícula de 1 px en `#2A3A30` (oscuro) o `#D5DED8` (claro). Sin bordes redondeados en celdas, sin sombras.
- Altura de fila: 32 px en escritorio, 44 px en tablet de estación (toque).
- Números con `font-variant-numeric: tabular-nums`, alineados a la derecha. Textos a la izquierda.
- Encabezados de columna en Barlow 500, 14 px, en una sola línea (sin envolver), con ancho fijo por columna.
- Letras de columna (A–M) y números de fila en una barra gris de 24 px y 48 px de ancho, sin borde redondeado.
- Celda seleccionada: borde verde láser de 2 px. Celda en edición: fondo `#15201A` y cursor de texto.
- Fila nueva: texto de sugerencia en gris ("Escribe y pulsa Enter") solo en la primera celda vacía.
- Franjas de color alternas: no. Las hojas reales no las tienen, y el plan visual ya prohíbe decorar.

Fijos:

- Columna de números de fila y encabezados fijos al hacer scroll (`position: sticky`).
- Columna B (# de orden) fija al desplazar en horizontal en tablet, para no perder la orden.

## 6. Accesibilidad

- La cuadrícula usa `role="grid"`, con `aria-rowcount` y `aria-colcount`, y cada celda con `role="gridcell"` y su letra y encabezado asociados (`aria-describedby`).
- Foco visible siempre en la celda seleccionada, con el mismo borde verde de 2 px.
- Las celdas de solo lectura declaran `aria-readonly="true"`.
- Mensajes de estado con `aria-live="polite"` en la barra inferior.
- Sin teclado, la app sigue funcionando con formularios por fila (ver sección 7, nivel 0).

## 7. Implementación por niveles

Así se evita que la hoja dependa por completo de JavaScript.

**Nivel 0: sin JavaScript.** Cada fila es un `<form>` con sus campos. Enter guarda la fila con el envío normal. Es el respaldo si el navegador bloquea el script.

**Nivel 1: con JavaScript externo (`web/static/sheet.js`).** Navegación por teclado, selección, barra de fórmulas, fila nueva al final, pegado desde hojas de cálculo y estado de guardado. Se guarda con `fetch` a la misma ruta de corrección que ya existe (`edit-production`), y el servidor sigue validando todo.

Cambios técnicos obligatorios:

- `web/app.py`: la CSP pasa a `script-src 'self'`. No se agrega `unsafe-inline`.
- `web/app.py`: `report_row` se sustituye por un renderizado de cuadrícula. Las columnas F–K salen del cálculo del servidor (`ledger.report_counts`), no del navegador.
- `web/app.py`: el botón "Corregir" y el "Eliminar" en `<details>` se quitan de cada fila. Eliminar pasa al menú de fila (clic derecho o botón ⋯ junto al número de fila), con la confirmación de hoy.
- `web/static/sheet.js`: nuevo, sin dependencias.
- `web/style.css`: reemplazar `.production-sheet` y `.sheet` por las reglas de cuadrícula de la sección 5.
- Ruta de guardado: sin ruta nueva para la celda. Se reutiliza `edit-production` con el registro completo para no duplicar reglas de validación.

## 8. Pruebas

Automatizadas (`tests/`):

- El servidor no sirve filas de otro láser al operario.
- Un operario recibe las celdas de otras filas como solo lectura, aunque mande un POST con esa fila.
- La CSP permite `script-src 'self'` y no `unsafe-inline`.
- Las columnas F, G, H, J y K no aceptan escritura desde el servidor.
- El total de la fila de totales coincide con la suma de confirmados.

Manuales, en tablet de cada turno:

- Escribir, Tab, Enter y flechas en una sesión completa de 30 filas sin tocar el mouse.
- Pegar 20 filas desde el sheet de Google y verificar que quedan en orden.
- Desconectar JavaScript y comprobar que el nivel 0 sigue guardando.

## 9. Orden de implementación

1. Ajustar la CSP y crear `web/static/sheet.js` vacío con el servicio de archivos estáticos.
2. Renderizar la cuadrícula en el servidor, sin JavaScript (nivel 0). Probar que se ve como hoja con las letras, los números y las columnas calculadas.
3. Agregar la navegación por teclado y la barra de fórmulas (nivel 1).
4. Agregar la fila nueva al final y el pegado desde hojas de cálculo.
5. Quitar los `<details>` por fila y pasar eliminar al menú de fila.
6. Pruebas automatizadas y prueba manual en tablet, en paralelo con el sheet (Fase 5 de `docs/PLAN.md`).

## 10. Decisiones que necesito confirmar

- [ ] ¿La columna **Operario** y **Estado** (de la app) van al final de la hoja, como se propone, o se ocultan para el operario?
- [ ] ¿Pegar desde Google Sheets se permite al operario, o solo al supervisor?
- [ ] ¿Las pestañas de hoja muestran todos los láseres del día para el supervisor, o solo el láser seleccionado?
