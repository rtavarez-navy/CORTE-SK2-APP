# CORTE SK2 · Versión web 0.1

Las estaciones abren una URL interna en el navegador. Para actualizar, publica la nueva revisión en el servidor central, conserva el archivo de datos y reinicia el servicio. Al recargar, las estaciones reciben la versión actual.

El desarrollador crea cuentas de supervisor y operador, asigna máquinas y puede registrar piezas en nombre de un operador asignado. El supervisor asigna láseres y puede crear, restablecer y dar de baja cuentas de operador. El desarrollador también puede gestionar supervisores. Restablecer devuelve la clave a `12345`, cierra las sesiones existentes y obliga a cambiarla en el próximo acceso. Dar de baja revoca el acceso, conserva el historial y reserva el código para esa identidad. El operador registra piezas en su máquina asignada. Cada láser admite dos operarios por fecha y turno. Al asignar un operario a una máquina o turno nuevo, queda trasladado desde su asignación anterior del día. El operario ve su estación y turno asignados. Si todavía no tiene asignación, aparece en Notificaciones.

El día de producción sigue la fecha de República Dominicana. El registro manual toma la referencia de orden o línea y cantidad. El resumen muestra el total capturado por turno y las máquinas asignadas. Una orden o línea repetida se detecta por la referencia completa, sin distinguir mayúsculas ASCII, incluso entre fechas. Queda pendiente y excluida de los totales hasta que un supervisor la conserve o la descarte en Notificaciones. El primer registro permanece confirmado. La validación de órdenes y cantidades con CPA queda para la integración posterior.

## Prueba local

Usa Python 3.11 o posterior en el servidor o entorno de desarrollo. Desde la raíz:

```bash
python -m pip install "fastapi>=0.115,<1" "uvicorn>=0.30,<1" tzdata
export CORTE_DEV_HTTP=1
export CORTE_DB=/ruta/privada/corte-sk2.sqlite3
python -m web.app CODIGO_EMPLEADO "Nombre del desarrollador"
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

Sustituye la ruta por un archivo en un directorio local que exista. El código conserva los ceros iniciales. Todas las cuentas entran con la contraseña inicial `12345` y la cambian antes de usar la aplicación. Completa el primer acceso junto con cada empleado al habilitar su cuenta, ya que el código y la contraseña inicial permiten reclamar una cuenta pendiente.

## Servidor de planta

Ejecuta Uvicorn detrás de HTTPS en la red interna, sin `CORTE_DEV_HTTP`. La base SQLite debe residir en disco local persistente del servidor. Conserva una copia de respaldo antes de cada actualización y mantén esa base fuera del repositorio. Si hay un proxy, configura Uvicorn para aceptar cabeceras reenviadas solo desde ese proxy, de forma que el límite de acceso por IP distinga las estaciones.

La aplicación arranca con `web.app:app`. Al actualizar desde una versión previa, el servidor migra automáticamente las plazas de los láseres y el estado de revisión. Los registros previos se conservan confirmados.
