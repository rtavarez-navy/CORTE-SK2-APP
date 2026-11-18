# CORTE SK2 APP — V0.1 inicial

**Estado:** código inicial para pruebas en entorno autorizado. No desplegado, no conectado todavía al CPA real y **no listo para producción empresarial sin validación de TI**.

## Qué incluye

- App de escritorio Windows en **PySide6**: sesión de operador, láser asociado a computadora, selección de turno, orden/línea/cantidad, consulta a CPA, registro y resumen semanal.
- **FastAPI** central con PostgreSQL: usuarios, asociación de estación, órdenes referenciadas de CPA, registros de producción y resumen.
- **Bloqueo de exceso:** bajo PostgreSQL se bloquea transaccionalmente la fila de orden/línea (`FOR UPDATE`) y se compara **la suma de todas las piezas registradas en todos los láseres y turnos** contra el límite CPA.
- **Registros repetidos:** cuando ya hay producción para la orden/línea se solicita confirmación; un reintento idéntico no duplica registros (UUID único).
- **CPA no disponible o desactualizado:** se rechaza el registro. Nunca se inventa una cantidad.
- **Compilación de `.exe` en la nube** con GitHub Actions en Windows. No necesitas instalar Python en tu computadora de desarrollo.

## Límite importante de esta versión

No se ha identificado el método real de conexión a CPA. Incluimos un **adaptador provisional de importación CSV** que funciona solo **si TI confirma que CPA puede exportar CSV con los campos `SO #`, `Set` y `Qty`**. El archivo de Google Sheets no se usa como base de datos ni como origen operacional. La integración en vivo será el siguiente ajuste cuando se conozca el acceso real autorizado.

El adaptador se diseñó con los **nombres de campos observados en la hoja de referencia**, no como prueba de que CPA genere ese formato. El contrato independiente `integrations/cpa_source.py` permite añadir `integrations/cpa_web.py` en el futuro sin alterar el cliente ni las reglas de producción; ver `docs/INTEGRACION_CPA.md`. El backend rechaza registros si una orden no existe en la fuente vigente o si su carga tiene más de `CPA_MAX_AGE_HOURS` horas (24 por defecto).

## Lo necesario para habilitar una prueba real

1. TI comprueba dónde se autoriza ejecutar FastAPI + PostgreSQL (puede ser `\\cs-600`, **no se asume**).
2. TI habilita una base PostgreSQL, HTTPS y cuentas operativas; define `DATABASE_URL`, `AUTH_SECRET`, `BUSINESS_TIMEZONE` y `CPA_MAX_AGE_HOURS` como variables de entorno del servidor (ver `.env.example`).
3. TI crea esquema inicial (`python -m backend.manage init-db`), cuenta (`python -m backend.manage add-user operador1`) y estación (`python -m backend.manage add-workstation 1`). Los comandos se ejecutan **en servidor autorizado o entorno de desarrollo en nube**, nunca requieren instalar programas en tu PC actual.
4. TI entrega de forma segura la clave de estación para colocarla en el archivo `C:\ProgramData\CORTE_SK2_APP\config.json` de la PC del láser indicado. Ver `desktop/config.example.json`. **No guardar las claves en GitHub.** La carpeta debe tener permisos restrictivos y la clave debe protegerse contra lectura no autorizada.
5. TI establece un método **verificado y autorizado de importación/consulta CPA**. Si se aprueba exportación CSV, importar con `python -m backend.manage import-cpa RUTA_AL_EXPORT.csv` en el servidor y programar la actualización fuera de GitHub. `sample-data/CPA_EJEMPLO.csv` contiene solo ejemplos ficticios y no debe usarse en operación real.
6. Se ejecutan pruebas en red interna y un piloto controlado. No se distribuye a empleados sin comprobar conectividad, seguridad, compatibilidad y recuperación de datos.

## Desarrollo desde navegador

1. Subir el contenido de este paquete a un repositorio **privado** de GitHub.
2. GitHub Actions ejecutará los tests de backend y, si pasan, creará `CORTE-SK2.exe` usando Windows.
3. En Actions → workflow **Pruebas y compilacion Windows** → descargar el artefacto `CORTE-SK2-Windows-V0.1`. La compilación no distribuye automáticamente nada a las PCs.
4. Si deseas modificar código, hacerlo desde el editor web de GitHub o Codespaces. Todo esto ocurre en nube.

## Desarrollo/test técnico (solo servidores, Codespaces o CI)

```bash
# En ambiente de desarrollo, nunca en la PC restringida
export DATABASE_URL='sqlite+pysqlite:///:memory:'
export AUTH_SECRET='SOLO_PRUEBAS_aleatorio_de_mas_de_32_caracteres'
python -m pip install -r requirements-backend.txt pytest httpx
pytest -q
```

**Importante:** SQLite se utiliza exclusivamente en tests locales del paquete; el servidor multiusuario debe utilizar PostgreSQL. La prueba definitiva de concurrencia se hará con PostgreSQL real.

Para ejecutar el backend en un servidor autorizado (después de configurar variables, base, usuarios y conexión CPA):

```bash
uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

En producción, publicar detrás de un proxy HTTPS autenticado/configurado por TI (puerto y host por determinar). No abrir el servidor al Internet público.

## Seguridad y pendientes antes de producción

- El acceso a CPA aún no es una integración viva; debe confirmarse antes del piloto con empleados.
- Proteger las credenciales y el secreto JWT, aplicar HTTPS con certificado confiable, cortafuegos, protección de inicio de sesión y políticas de sesión.
- Establecer permisos estrictos para el token de cada computadora; evaluar emparejamiento y revocación de dispositivos según TI.
- Diseñar y aprobar migraciones de esquema, respaldos, restauración probada, monitoreo y auditoría operativa.
- Validar que `Set` y `Qty` del origen autorizado representan exactamente la línea y el máximo permitido.
- Confirmar tratamiento de reprints. Hasta entonces, todo registro descuenta de la cantidad normal autorizada en CPA.
- Validar fecha de producción para los turnos nocturnos. En V0.1 la fecha se toma del reloj del servidor.
- GitHub almacena código, no datos empresariales ni credenciales.
- Sin actualizador automático todavía: se añadirá cuando la primera versión de registro esté validada.

## Estructura

```text
backend/             API, seguridad, modelos, administración
integrations/        Contrato de fuente CPA y carga CSV provisional
 desktop/            Aplicación PySide6 Windows
 tests/              Pruebas automatizadas de reglas centrales
 docs/               Notas de implementación
 .github/workflows/  CI y compilación Windows
```

## Comportamiento confirmado

- Cada láser tiene una computadora asignada.
- El operador puede cambiar de máquina y autenticar su sesión en la nueva PC.
- Registra al terminar orden y línea.
- Orden/línea repetida: advertencia + confirmación, si aún caben piezas.
- Producción acumulada de orden/línea **no puede exceder** el máximo que devuelve CPA.
