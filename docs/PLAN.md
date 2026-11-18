# Plan CORTE SK2 · app de producción

Reemplazo del sheet "Corte Sakira 2" por una app web en la que cada operario solo ve y edita su láser asignado.

## Estado actual del repositorio (18/11/2026)

- App FastAPI con SQLite. Roles: desarrollador, supervisor y operador.
- Registro manual de piezas con referencia (orden o línea), operario y cantidad.
- Detección de duplicados por referencia completa; los repetidos quedan pendientes hasta que un supervisor los confirme o descarte.
- Consulta CPA de solo lectura (`web/cpa.py`): busca una orden en la base SQLite que actualiza URA, filtrada por fábrica (`JuiceSakira2` por defecto). Muestra Set, cantidad CPA y estado de línea. Se configura con `CPA_DB`.

## Diferencias clave con la app actual

1. **Visibilidad por láser.** Hoy el operario solo ve sus propias piezas dentro de su láser. Debe ver todas las filas de su láser y turno, incluidas las de su compañero.
2. **Editar y eliminar.** Hoy solo se puede agregar. Hace falta corregir y borrar registros propios, con historial de cambios.
3. **Columnas.** La app guarda una sola referencia. Hay que separar orden y línea, y agregar fecha, comentarios, reprint, SKU, repeticiones y estado CPA.
4. **Datos históricos.** La pestaña Historia tiene unas 128 mil filas. Hay que decidir si se migran o si se empieza desde cero.

## Columnas objetivo (las del sheet)

Cada pestaña de láser tiene: FECHA, # DE ORDEN, LINEA, # PIEZAS, COMENTARIOS, * REPRINT *, Orden + Linea, REPETICIONES, SKU, CPA (SUPERVISOR), DUP.

## Plan por fases

**Fase 0: Decisiones.** Alcance del reemplazo, historial a migrar, permisos de edición y servidor de despliegue.

**Fase 1: Modelo de datos.** Un registro por pieza con fecha, turno, láser, orden, línea, piezas, comentarios, reprint, SKU, repeticiones, operario, estado y auditoría. Migración de la base actual sin perder registros confirmados.

**Fase 2: Reglas de acceso.** Operario: ve y edita solo su láser asignado en su turno. Supervisor: ve todos los láseres, asigna operarios y revisa duplicados. Pruebas que verifiquen que un operario no lee ni escribe en otro láser.

**Fase 3: Diseño para planta.** Pantallas para tablet o estación con captura rápida y búsqueda por orden. Vista de reporte con las mismas columnas del sheet y totales por día y turno. Se diseña con el skill de diseño frontend.

**Fase 4: Duplicados y reprints.** Replicar Orden + Línea, REPETICIONES, DUP. y * REPRINT * con las reglas del sheet, que hay que confirmar revisando sus fórmulas.

**Fase 5: Migración y despliegue.** Importar el historial elegido, respaldo antes de cada actualización, HTTPS en red interna y prueba en paralelo con el sheet antes de apagarlo.

**Fase 6: Integración con CPA.**
- Ya hecho: consulta de solo lectura por orden desde el reporte de láser.
- Pendiente: usar CPA para llenar la columna CPA (SUPERVISOR) y validar cantidades al registrar, en lugar de solo consultar.
- Pendiente: confirmar con URA el esquema real de `cpa_lines` (los nombres de columna y si la cantidad CPA es la correcta para cada línea).
- Pendiente: decidir qué pasa cuando CPA dice "NO EXISTE EN EL CPA" o cuando la cantidad no coincide.

## Próximo paso

Cerrar la Fase 0 con estas tres respuestas:

- [ ] Alcance: ¿reemplaza todas las pestañas o solo el reporte de producción?
- [ ] Historial: ¿se migra Historia completa, desde una fecha o nada?
- [ ] Permisos: ¿quién puede editar registros de otros o solo los propios?
