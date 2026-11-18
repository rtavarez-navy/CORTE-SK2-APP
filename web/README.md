# CORTE SK2 · Versión web 0.1

Las estaciones abren una URL interna en el navegador. Para actualizar, publica la nueva revisión en el servidor central, conserva el archivo de datos y reinicia el servicio. Al recargar, las estaciones reciben la versión actual.

El desarrollador crea cuentas de supervisor y operador, asigna máquinas y puede registrar piezas en nombre de un operador asignado. El supervisor asigna láseres y puede crear, restablecer y dar de baja cuentas de operador. El desarrollador también puede gestionar supervisores. Restablecer devuelve la clave a `12345`, cierra las sesiones existentes y obliga a cambiarla en el próximo acceso. Dar de baja revoca el acceso, conserva el historial y reserva el código para esa identidad. El operador registra piezas en su máquina asignada. Cada láser admite dos operarios por fecha y turno. Al asignar un operario a una máquina o turno nuevo, queda trasladado desde su asignación anterior del día. El operario ve su estación y turno asignados. Si todavía no tiene asignación, aparece en Notificaciones.

El día de producción sigue la fecha de República Dominicana. El registro manual captura orden, línea, cantidad, SKU y comentarios. El resumen muestra el total capturado por turno y las máquinas asignadas. Las repeticiones se detectan por la clave de orden y línea, incluso entre fechas. Queda pendiente y excluida de los totales hasta que un supervisor la conserve o la descarte en Notificaciones. El primer registro permanece confirmado. La validación de órdenes y cantidades con CPA queda para la integración posterior.

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

## Alcance del piloto

CORTE SK2 reemplaza el registro de producción diario por láser y turno. Cada operario puede consultar todas las filas de la estación asignada y corregir o retirar sus propios registros durante el día de trabajo. El supervisor consulta todos los turnos, asigna personal y revisa duplicados. Las correcciones de terceros quedan reservadas al desarrollador. El historial de cambios registra responsable, fecha y valores anteriores y nuevos.

Se conservan los registros del SQLite existente. La migración separa las referencias antiguas cuando reconoce una orden numérica seguida de un Set alfabético. Las referencias ambiguas conservan el texto original y quedan sin línea hasta que se corrijan. El piloto comienza sin importar la pestaña Historia. El Sheet sigue disponible para consultar el histórico.

### Reglas de producción

- **Orden + Línea** concatena el número sin prefijo SO- y la línea en mayúsculas.
- **Repeticiones** cuenta la clave en el mismo láser y turno. **Dup.** la cuenta en toda la producción de la app. Las dos columnas abarcan los días guardados en la app y excluyen descartes y eliminaciones.
- Un registro repetido queda pendiente. El supervisor lo confirma o descarta desde Notificaciones. Los totales incluyen solo los confirmados.
- **Reprint** muestra un asterisco cuando la clave está en Personal → Reprints válidos. El supervisor mantiene ese listado y la autorización no sustituye la revisión de duplicados. Carga allí las autorizaciones del Sheet que sigan vigentes durante el piloto.
- El SKU y los comentarios se capturan manualmente. La consulta directa a CPA se hace en la caja del reporte. La columna **CPA (Supervisor)** del registro se reserva para una validación posterior.

### Actualización y prueba en paralelo

1. En el servidor, conserva la ruta actual de `CORTE_DB`. Con el código actualizado y antes de iniciar Uvicorn, crea un respaldo SQLite consistente. Usa un archivo nuevo en una carpeta protegida que ya exista:

   ```bash
   python -m web.backup /ruta/privada/corte-sk2-antes-del-cambio.sqlite3
   ```

2. Arranca la aplicación en la red interna detrás del proxy HTTPS con almacenamiento persistente y sin `CORTE_DEV_HTTP`. Confirma con el equipo de planta el host y diez minutos de prueba desde una estación de cada turno.
3. Durante las jornadas de piloto acordadas con planta, conserva el Sheet en operación. Compara diariamente fecha, turno, láser, orden, línea, piezas confirmadas, reprints y decisiones de duplicados. Verifica el flujo con dos operarios y una corrección de registro antes de autorizar el cambio definitivo.
4. Si se necesita revertir, detén el servidor, conserva una copia de la base posterior al cambio y arranca la versión anterior apuntando a una copia del respaldo anterior.

### Pruebas automatizadas

```bash
python -m pip install httpx
python -m unittest discover -s tests -v
```


## Consulta directa a CPA

Desde el reporte del láser, escribe `3986055 A` en **Orden y línea**. La app busca `3986055` en Production Lines y muestra solo el Set `A` de JuiceSakira2. Si omites el Set, muestra las líneas que CPA devuelve para la orden. Sale de la tabla del portal, como consulta de solo lectura.

Para habilitarla, prepara Playwright y Chromium en el servidor que ejecuta CORTE SK2:

```bash
python -m pip install playwright
python -m playwright install chromium
export CORTE_CPA_STATE=/ruta/privada/corte-cpa-session.json
python -m web.cpa
```

Ejecuta el último comando en un entorno gráfico con la misma cuenta del sistema que ejecutará la app, inicia sesión en el navegador abierto y pulsa Enter cuando aparezca Production Lines. Usa una cuenta de CPA autorizada para la consulta de producción en Sakira 2. Mantén el archivo de sesión fuera del repositorio y con acceso restringido a esa cuenta del sistema, pues contiene la sesión de CPA.

Arranca Uvicorn con `CORTE_CPA_STATE` apuntando al mismo archivo y un solo worker. Para renovar una sesión vencida, detén la app, vuelve a ejecutar `python -m web.cpa` e inicia el servidor otra vez.
