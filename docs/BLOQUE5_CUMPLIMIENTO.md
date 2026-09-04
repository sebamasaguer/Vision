# Bloque 5 v0.6.0 — Motor Inteligente de Cumplimiento

## Flujo
PERSON → TRACK → ZONA → REGLA → EPP → ventana temporal → consenso → SafetyDetectionEvent.

## Principios
- `NO_VISIBLE` e `INCIERTO` son `UNKNOWN`: no generan evento.
- EPP no soportado por el modelo activo es `NO_APLICA`.
- Sólo reglas `REQUIRED` activas y dentro de horario son evaluables.
- Zonas superpuestas se consolidan por EPP y gana la regla REQUIRED de mayor severidad.
- Dedupe por `camera + track + EPP`.
- Un evento OPEN se actualiza; no se recrea por cada frame.
- Al corregirse la condición se cierra tras `clear_grace_seconds`.
- Si desaparece el track se cierra tras `track_absence_close_seconds`.
- Cooldown evita reapertura inmediata.
- El motor queda desactivado por defecto en cada cámara y requiere habilitación explícita.
- Safety Events son detecciones preventivas, no sanciones ni decisiones laborales.

## Persistencia temporal por defecto
- Ventana: 4 s
- Persistencia continua mínima: 2 s
- Observaciones faltantes mínimas: 3
- Consenso mínimo: 70 %
- Cooldown: 15 s
- Gracia de corrección: 1 s
- Cierre por ausencia de track: 3 s

`NO_VISIBLE`, `INCIERTO` y `OK` interrumpen la secuencia continua de `NO_DETECTADO`; por eso una oclusión breve no suma tiempo de incumplimiento.

## Persistencia
- `safety_detection_events`: evento deduplicado OPEN/CLOSED.
- `compliance_evaluations`: historial compacto por transición de estado y máximo 1 muestra/s por clave.

## API
- `GET /api/v1/safety-events`
- `GET /api/v1/safety-events/summary`
- `GET /api/v1/safety-events/evaluations`
- `GET /api/v1/safety-events/{id}`

La revisión humana, evidencia, WebSocket y acciones de cierre manual se completan en los bloques 6 y 7.
