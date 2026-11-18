# Validaciones V0.1

## Flujo de registro

1. El empleado inicia sesión y el backend identifica la máquina mediante su token individual (no por una selección editable de láser).
2. Ingresa turno T1/T2, número de orden, línea y piezas.
3. Se consulta la fuente CPA vigente para esa orden/línea. Si no existe o está vencida, **no se permite** registrar.
4. Se inicia una transacción de PostgreSQL con bloqueo de la fila de CPA correspondiente.
5. Se suma la producción existente de esa orden/línea **sin separar máquina ni turno**.
6. Si acumulado + nuevo > máximo CPA, se rechaza siempre.
7. Si hay registros anteriores, exige confirmación explícita.
8. Si es válida, guarda cantidad, usuario, máquina, turno, fecha y si confirmó repetición, y confirma la transacción.
9. El mismo `request_id` no puede crear dos registros (idempotencia de reintentos de red).

## Decisiones abiertas

- Método real de acceso a CPA; se requiere revisión técnica con TI.
- Reprints: todavía no existe una regla autorizada para admitir exceso especial.
- Horarios reales de turno y fecha contable para T2 al cruzar medianoche.
- Proceso para anular o corregir registros; V0.1 no permite borrar ni editar producción desde la UI.
- La política definitiva de asignación y custodia de los tokens de estación.

## Notas de ingeniería

- La prueba automatizada SQLite cubre reglas de negocio, no demuestra serialización multiusuario. La prueba de concurrencia final deberá ejecutarse en un PostgreSQL autorizado.
- Una actualización de la cantidad CPA a un valor inferior a la producción ya registrada se rechaza en el importador provisional, sin alterar los datos anteriores.
- El resumen se genera con una consulta a registros centrales, no con fórmulas ni copias a Sheets.
