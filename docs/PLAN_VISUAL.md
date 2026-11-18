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

Decidido: modo oscuro en estación y resumen, y modo claro en reporte e impresión.

Decidido: las variantes se exportan como PNG a partir del WebP original. La cabecera usa el león a 40 px con una imagen de 80 px y texto seleccionable.

## 11. Orden de implementación

1. Preparar los recursos del logo en `web/static/` (sección 7).
2. Definir variables de color y tipografía en `web/style.css`, con la fuente Barlow alojada localmente (sin CDN, porque la planta puede estar sin internet).
3. Rediseñar la cabecera y el inicio de sesión.
4. Rediseñar la estación del operario, que es la pantalla más usada.
5. Rediseñar el resumen y las tarjetas de láser.
6. Rediseñar el reporte y la prueba en tablet de cada turno antes de dar por cerrada la Fase 3.
