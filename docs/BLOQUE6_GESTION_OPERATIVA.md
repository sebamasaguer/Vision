# Bloque 6 v0.7.0 — Gestión Operativa de Alertas y Evidencias

- Evidencia automática al confirmar Safety Event: snapshot raw, snapshot anotado y clip previo cuando hay buffer suficiente.
- MinIO + SHA-256 + claves content-addressed. La API no expone modificación ni borrado de evidencia.
- Estados operativos: NEW, ACKNOWLEDGED, IN_REVIEW, RESOLVED.
- Resultados de revisión: PENDING, CONFIRMED, FALSE_POSITIVE.
- Asignación de responsable, notas append-only, reconocimiento, revisión y resolución.
- Timeline específico por evento + AuditLog global.
- Separación entre estado técnico de detección OPEN/CLOSED y estado operativo humano.
- No hay sanciones automáticas, notificaciones multicanal ni escalamiento SLA en este bloque.

La inmutabilidad de evidencia es de aplicación (sin endpoints update/delete y con hash SHA-256). Para WORM regulatorio se deberá configurar Object Lock/retention en infraestructura antes de una certificación formal.
