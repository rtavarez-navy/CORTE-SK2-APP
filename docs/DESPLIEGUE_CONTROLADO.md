# Lista de control para TI antes de habilitar usuarios

- [ ] Servidor y sistema operativo autorizados; recursos y disponibilidad revisados.
- [ ] PostgreSQL autorizado; accesible **solo por backend**; usuarios y backups definidos.
- [ ] Backend FastAPI como servicio administrado con reinicio automático y logs.
- [ ] HTTPS interno con certificado confiable, firewall, DNS y TLS de extremo a extremo donde corresponda.
- [ ] Origen CPA real conocido y autorizado. Importador CSV solo si TI certifica que es un export válido y se renueva dentro de plazo.
- [ ] Usuarios, contraseñas y estaciones emparejadas por TI; permisos sobre `config.json`.
- [ ] Protección contra ataques de fuerza bruta en el ingreso (proxy o mecanismo corporativo).
- [ ] Pruebas simultáneas en PostgreSQL confirmadas: nunca supera cantidad CPA.
- [ ] Pruebas de caída del servicio: error visible y sin registro falso.
- [ ] Pruebas de doble clic/reintentos: mismo UUID no duplica.
- [ ] Política de respaldo/restore; migraciones y documentación.
- [ ] Piloto de una PC/láser aprobado.

**No se debe usar este código en producción hasta completar estas validaciones.**
