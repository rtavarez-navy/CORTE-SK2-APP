# Diseño final · CORTE SK2

Este documento reúne el plan visual general y el diseño de la hoja de cada láser.

---

# Plan de dirección visual · CORTE SK2

Objetivo: que la app se vea profesional y moderna, con el logo como punto de partida, y que se pueda usar sin errores en una estación de planta con guantes, polvo y mala iluminación.

Este documento es la Fase 3 de `docs/PLAN.md` hecha concreta. Define la paleta, la tipografía, el layout y los principios. La implementación va después, en `web/style.css` y en las plantillas de `web/app.py`.

## 1. Punto de partida: el logo

El logo tiene tres ideas que la interfaz debe conservar:

- Un león verde con melena de hojas. Es el símbolo de la marca y va en la cabecera.
- Una cuchilla plateada que cruza la cara del león. Es lo único brillante del logo y el elemento más memorable: la app lo usará como línea de corte.
- Un fondo casi negro con verde eléctrico y un subtítulo "CORTE SAKIRA 2 & Proyecto Ámbar" en rojo ámbar. La marca muestra siempre ambos nombres: CORTE SAKIRA 2 y Proyecto Ámbar.

Dirección elegida: **taller de corte de precisión**. Oscuro, sobrio, con una sola pieza de brillo (la línea plateada). No es un panel genérico verde. Es una herramienta de planta que se ve cuidada.

## 2. Paleta

| Rol | Nombre | Hex | Uso |
|---|---|---|---|
| Fondo | Taller | `#0C1410` | Fondo de página en modo planta |
| Superficie | Mesa | `#15201A` | Tarjetas, tabla, barra de captura |
| Acento | Láser | `#3DD65A` | Estado activo, foco, botón principal |
| Acento profundo | Hoja | `#1F7A3A` | Bordes de selección, fondos de estado |
| Metal | Cuchilla | `#C7D2CC` | Texto principal, líneas de corte, divisores |
| Alerta | Ámbar | `#E0392F` | Duplicados, errores, láseres sin operario |

Reglas:

- Texto principal `#C7D2CC` sobre `#0C1410`: contraste de unos 12:1. Pasa AAA.
- El verde `#3DD65A` solo marca lo que se puede tocar o lo que está activo. Nunca decora.
- El rojo ámbar tiene dos usos: el nombre "Proyecto Ámbar" en la marca, y las alertas. Para que la alerta no se confunda con la marca, la alerta es siempre un bloque con fondo rojo tenue, borde y texto explícito ("Duplicado", "Sin operario"), nunca solo un texto rojo.
- Si todo está en alerta, nada lo está.
- Modo claro para reporte e impresión: mismo verde profundo `#1F7A3A` como acento, sobre papel `#F4F7F5`, con texto `#0C1410`. Las alertas usan el mismo rojo `#E0392F` con fondo tenue. Ambos modos comparten nombres de color y reglas.
- Modo oscuro para estación y resumen; modo claro para reporte e impresión. El usuario lo eligió así en ambos sentidos: se implementan los dos.

## 3. Tipografía

Una sola familia con dos anchos, para que el logo y la interfaz hablen el mismo idioma:

- **Barlow Condensed 700** para títulos, nombres de láser y cifras grandes. Recuerda las letras cortadas del logotipo.
- **Barlow 400 / 500** para texto de trabajo, formularios y tablas.
- Cifras con `font-variant-numeric: tabular-nums` en todas las columnas de piezas. Los números de producción deben alinearse hacia la derecha.

Escala (base 16 px):

- Cifra grande de KPI: 56 px, Condensed 700.
- Título de página: 32 px, Condensed 700.
- Nombre de láser en tarjeta: 22 px, Condensed 600.
- Texto de trabajo y tabla: 16 px, Barlow 400. En estación, 18 px.
- Texto de apoyo: 14 px, Barlow 500, color `#8FA196`.

No se usan mayúsculas sostenidas en etiquetas. Las etiquetas van en oración normal ("Fecha de producción"). Las columnas del sheet conservan sus nombres originales (`# DE ORDEN`, `CPA (SUPERVISOR)`) porque el personal ya los conoce, así que ahí no se cambian.

## 4. Layout

Tres pantallas, en este orden de importancia:

**a) Estación (operario, tablet).** Es la pantalla más usada. Debe poder usarse con una mano.

```
┌──────────────────────────────────────────────────────────────┐
│ [león]  CORTE SK2 · Láser 4 · Turno 1          Cerrar sesión │
│ ──────────────── cuchilla (línea 1 px) ──────────────────────│
│                                                              │
│  Orden [______________]  Línea [____]  Piezas [____]  [Guardar]│
│  Comentario [__________________________________]              │
│                                                              │
│  FECHA   # ORDEN   LINEA   # PIEZAS   COMENTARIOS   DUP.     │
│  ───────────────────────────────────────────────────────────  │
│  18/11   SO-4471   B       120        —                 ·     │
│  18/11   SO-4472   A        80        reprint *         ·     │
│  ...                                                          │
└──────────────────────────────────────────────────────────────┘
```

- La barra de captura va arriba y ocupa todo el ancho. Campos de 52 px de alto.
- La tabla usa las mismas columnas que el sheet, en el mismo orden. La cabecera queda fija al hacer scroll.
- Las filas de otros operarios del mismo láser se ven en gris medio. Las propias, en la superficie normal. Así se distingue quién cargó qué sin leer el nombre.

**b) Resumen (supervisor).** Pantalla de inicio. Lo que importa es el estado de la planta de un vistazo.

```
┌──────────────────────────────────────────────────────────────┐
│ Piezas hoy        Turno 1        Turno 2       Por revisar   │
│ 12,480            6,210          6,270         3             │
│──────────────────────────────────────────────────────────────│
│ Láser 1 ▌ 2 operarios   Láser 2 ▌ 1 operario   Láser 3 ▌ —   │
│ Láser 4 ▌ 2 operarios   ...                                  │
└──────────────────────────────────────────────────────────────┘
```

- Las tarjetas de láser no son todas iguales. Una franja vertical de color a la izquierda marca el estado: verde si tiene dos operarios, ámbar si tiene uno, rojo si no tiene ninguno. Es la única variación de tarjeta; no hay redondeos distintos por tipo de elemento.
- El aviso de duplicados aparece como fila de cabecera, no como tarjeta.

**c) Reporte (supervisor).** Tabla densa con las columnas del sheet, filtros por fecha y turno, y totales al pie por día. Sin gráficas decorativas. Si se necesita un gráfico de progreso, va una barra por turno.

Alineación: todo a la izquierda, excepto cifras, que van a la derecha. No hay texto centrado en tablas ni en formularios.

Estructura: no hay pasos numerados. Las pantallas no son una secuencia, así que no llevan `01 / 02 / 03`.

## 5. Principios

1. **El logo es la única ilustración.** La cabecera muestra el león y el texto "CORTE SAKIRA 2 & Proyecto Ámbar" a tamaño pequeño; el icono del navegador es solo el león. No se repite en el fondo ni en las tarjetas.
2. **La cuchilla es el único brillo.** Una línea plateada de 1 px separa la cabecera del contenido. Es el gesto de marca. No se usan degradados como decoración.
3. **Las cifras mandan.** Piezas, totales y estado se leen antes que cualquier etiqueta.
4. **Ninguna pantalla depende del color solo.** Cada estado tiene texto además del color ("Duplicado", "Sin operario"), para planta con daltonismo o pantalla con mal brillo.
5. **Una sola animación.** Al entrar, la línea plateada de la cabecera se dibuja de izquierda a derecha en 400 ms. Nada más se anima. Con `prefers-reduced-motion`, la línea aparece sin animación.
6. **Textos de la interfaz en lenguaje de planta.** Verbos claros y mismo nombre en todo el flujo: el botón "Guardar pieza" produce el aviso "Pieza guardada". Los errores dicen qué pasó y qué hacer: "Esta orden ya está registrada hoy en el láser 4. Espera revisión del supervisor."
7. **Calidad mínima sin anunciarla:** foco visible en todo elemento interactivo, objetivos táctiles de 44 px o más, contraste AA como mínimo, responsive desde 360 px de ancho.

## 6. Cambios concretos sobre el código actual

Lo que hoy se ve genérico y se corrige:

- `web/app.py`: la cabecera usa `✳` y el texto "CORTE **SK2**". Se reemplaza por el lockup del logo: león, "CORTE SAKIRA 2" en Condensed 700 y "& Proyecto Ámbar" en rojo ámbar debajo, en versión pequeña. Se quita el eyebrow "CORTE · SAKIRA 2" en mayúsculas sobre cada título, porque la cabecera ya dice el nombre.
- `web/style.css`: el tema es claro y verde pálido, sin identidad. Se define el tema oscuro de planta con las variables de la sección 2.
- Tarjetas `section`, `article` y `.laser-card` tienen el mismo radio y la misma sombra. Se reducen a una sola regla por nivel: superficie sin sombra, borde 1 px, radio 8 px.
- Botones con `#e4f5e7` y texto verde oscuro: pasan a botón de acento `#3DD65A` con texto `#0C1410`.

## 7. Recursos del logo

- Del logo original (fondo oscuro, `.webp`) se necesita:
  - Versión del león sin el texto, en PNG con fondo transparente, para la cabecera (alto 40 px).
  - Versión cuadrada del león para favicon (32 y 180 px).
  - Versión completa del logotipo, con "CORTE SAKIRA 2 & Proyecto Ámbar", para la pantalla de inicio de sesión.
  - Versión del lockup pequeño (león + textos) para la cabecera, en PNG 2x.
- Idealmente se vectoriza el león (SVG). Si no, se exporta en 2x desde el original.
- Dónde se guardan: `web/static/` con `logo-mark.png`, `logo-full.png` y `favicon.png`. Se sirven desde FastAPI como el CSS.

## 8. Referencia externa

La captura de "Project Tracker Dashboard" sirve para la **estructura** del resumen: fila de KPI arriba, filtros a la izquierda, tabla de detalle abajo, barra de progreso por línea. No se copian sus colores, su tipografía ni su marca ("Excel with Christy"). El verde de esa captura es genérico; el nuestro sale del logo.

## 9. Revisión del plan contra los defaults

Antes de codificar se revisó el plan contra un diseño genérico de app de producción. Cambios hechos:

- **Tema oscuro verde como única identidad.** Ya era la dirección del logo, pero el primer borrador usaba negro tintado sin relación con la marca. Se cambió a `#0C1410`, tomado del fondo del logo.
- **Sin tarjetas iguales.** El primer borrador ponía todas las tarjetas de láser con el mismo estilo. Se añadió la franja de estado para que la tarjeta informe.
- **Sin etiquetas en mayúsculas ni eyebrows.** Se quitaron.
- **Sin numeración.** Las pantallas no son pasos. Se quitó la numeración que sugería un flujo.

## 10. Decisiones pendientes

Decidido: la marca muestra "CORTE SAKIRA 2 & Proyecto Ámbar" en la cabecera y en el inicio de sesión.

Pendientes:

Decidido: modo oscuro en estación y resumen, y modo claro en reporte e impresión.

Pendiente:

- [ ] ¿Se entrega el logo vectorizado o basta un PNG en 2x? Propuesta: PNG en 2x ahora, SVG cuando haya presupuesto para vectorizar.

## 11. Orden de implementación

1. Preparar los recursos del logo en `web/static/` (sección 7).
2. Definir variables de color y tipografía en `web/style.css`, con la fuente Barlow alojada localmente (sin CDN, porque la planta puede estar sin internet).
3. Rediseñar la cabecera y el inicio de sesión.
4. Rediseñar la estación del operario, que es la pantalla más usada.
5. Rediseñar el resumen y las tarjetas de láser.
6. Rediseñar el reporte y la prueba en tablet de cada turno antes de dar por cerrada la Fase 3.

## Complemento

El diseño detallado de la hoja de cada láser (cuadrícula, teclado, fórmulas y pruebas) está en `docs/PLAN_HOJA_LASER.md`.


---

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
| L | Operario | automática | no | Se llena sola con el código del operario que registra. Oculta para el operario; visible y editable solo para supervisor y desarrollador |
| M | Estado | de la app | no | Confirmado, Por revisar o Descartado. Visible para todos |

Las columnas F, G, H, J y K llevan fondo `#101A14` y texto `#8FA196`. Son lo que en una hoja sería una fórmula: se distinguen a simple vista de lo que se escribe.

### Barra de fórmulas

Al seleccionar una celda, la barra superior muestra:

- A la izquierda, la referencia de la celda (por ejemplo `B12`).
- A la derecha, el contenido. En una celda de dato, el valor. En una celda calculada, la fórmula en texto, por ejemplo `=SIN_SO(B12)&"-"&C12`. Es la pista que hace que la columna se lea como hoja.

### Fila nueva

Siempre hay una fila vacía al final, como en el sheet. Escribir en ella y pulsar Enter crea el registro y deja una fila nueva abajo. La fila nueva no aparece con formulario encima; es la última fila de la cuadrícula.

La columna L (Operario) se llena sola. El operario no la ve ni la escribe. El supervisor la ve y puede corregirla si un registro quedó a nombre de otra persona.

## 2b. Ciclo semanal e hoja de Historia

Cada hoja de láser es la semana en curso. No hay que empezar de cero cada día.

- **Semana:** empieza el lunes y termina el domingo, en zona horaria de República Dominicana.
- **Selector de semana (supervisor):** un selector de semana en la parte superior de la hoja del láser. Por defecto muestra la semana actual. El supervisor puede elegir cualquier semana anterior guardada en Historia, y la hoja de esa semana se muestra igual que la actual, en modo solo lectura.
- **Operario:** ve solo la semana actual de su láser y turno. No tiene selector de semana.
- **Cierre:** al terminar el domingo a las 23:59, una tarea programada archiva todas las filas de la semana en la hoja **Historia** y vacía la hoja del láser para la semana siguiente.
- **Historia:** una sola hoja con todos los registros de todas las semanas, con las mismas columnas más Láser, Turno, Semana y Operario. Es de solo lectura. Solo el desarrollador puede corregirla, y cada corrección queda en el historial de cambios.
- **Datos en la semana:** el número de la semana (por ejemplo, `2026-S47`) se guarda en cada registro. Así Historia y la hoja semanal salen de la misma tabla y no hay que copiar datos a mano.
- **Migración:** la pestaña Historia del sheet (unas 128 mil filas) se importa a la hoja Historia como primer paso. Eso resuelve la decisión de Fase 1 de `docs/PLAN.md`.
- **Reglas que cruzan semanas:** *Repeticiones* y *Dup.* siguen contando en toda la historia, no solo en la semana actual. Si una orden se repite en una semana distinta, la fila queda por revisión como antes.
- **Respaldo antes del cierre:** la tarea de cierre hace un respaldo de la base antes de mover las filas. Si falla, no vacía la hoja y avisa al supervisor en Notificaciones.

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

Pegar desde una hoja de cálculo de Google Sheets (texto separado por tabulaciones) crea varias filas. Eso ahorra captura y permite migrar un día del sheet en un solo paso. Solo el supervisor puede pegar; para el operario, Ctrl+V queda desactivado y la barra de estado indica que pegar lo hace el supervisor.

Las celdas bloqueadas (filas de otro operario, columnas calculadas) se pueden seleccionar para leer la fórmula o el valor, pero no escribir. Al intentar escribir, la barra de estado dice "Esta celda no se puede editar" en lugar de no responder.

## 4. Permisos visibles

- **Operario:** ve todas las filas de su láser y turno de la semana. Puede editar solo sus filas. Las demás aparecen en tono apagado (`#516359` sobre fondo de hoja) sin cursor de edición. No ve la columna L (Operario), que se llena sola.
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
6. Agregar la semana (`week`) a cada registro y la vista semanal por láser y turno.
7. Crear la hoja Historia y su importación desde la pestaña Historia del sheet.
8. Tarea de cierre semanal con respaldo previo y aviso en Notificaciones si falla.
9. Pruebas automatizadas y prueba manual en tablet, en paralelo con el sheet (Fase 5 de `docs/PLAN.md`).

## 10. Decisiones que necesito confirmar

Decidido:

- Columna **Operario** automática y oculta para el operario. **Estado** visible para todos.
- Cada hoja de láser es la semana en curso. Al cerrar la semana, las filas pasan a la hoja **Historia**.
- La semana va de lunes a domingo. El supervisor elige la semana a ver con un selector; el operario ve solo la actual.
- Las pestañas del supervisor muestran todos los láseres que tengan al menos una pieza en la semana que está viendo. Un láser sin piezas esa semana no aparece como pestaña.

Pendiente:
Decidido: pegar desde Google Sheets lo hace solo el supervisor.
