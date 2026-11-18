# CPA — punto de integración futuro (sin implementar acceso web)

CPA es una **página web**. Esta versión no inicia sesión, no automatiza el sitio y no tiene una API de CPA confirmada. No se deben almacenar contraseñas ni cookies de CPA en el cliente Windows ni en GitHub.

## Contrato que debe respetar una integración futura

`integrations/cpa_source.py` define:

- `CPALimit(order_number, line, pieces)` como representación normalizada del límite de cada línea.
- `CPASource.fetch_limits()` como método de lectura de una fuente CPA autorizada.
- `sync_cpa_source(db, source)` como función de aplicación transaccional de cambios a la tabla `cpa_orders`.

Implementar un proveedor web en **un nuevo archivo** `integrations/cpa_web.py` (cuando TI confirme el método autorizado) y desde una tarea del backend invocar `sync_cpa_source(db, proveedor)`. La interfaz Windows y los endpoints `/orders/...`, `/production` y `/summary` no necesitan cambiar.

## Seguridad y comportamiento

- La adquisición de datos CPA se ejecuta **en el servidor**, no en las estaciones láser.
- Requerimos orden, línea/set y cantidad máxima validada; el nuevo proveedor debe normalizar estos campos.
- Si un límite de CPA baja por debajo de las piezas ya registradas, la actualización se rechaza, sin alterar registros existentes.
- Las órdenes sin datos en el caché local, o con datos vencidos, se bloquean para producción. Nunca inventar límites.
- No asumir que CPA tiene API pública. Usar únicamente el método aprobado por el propietario de CPA/TI.
- La primera versión incluye `integrations/cpa_csv.py` solo para pruebas/importaciones autorizadas.

## Validación futura

Probar la obtención de orden/línea, los límites, ausencia de datos, desactualización, fallos de autenticación y sincronización concurrente contra PostgreSQL antes del despliegue real.
