# Arquitectura — HYS Vision IA v0.8.0

```text
Cámaras / MP4 / RTSP
        ↓
 camera-worker
        ↓ Redis frames
 vision-engine
        ↓
 PERSON → TRACK → ZONA → EPP → cumplimiento
        ↓
 SafetyDetectionEvent
        ↓                         ↘ MinIO evidencias
 PostgreSQL                       
        ↓
 alert-worker ← Redis heartbeat
        ↓
 SLA / escalamiento / deliveries
        ↓
 IN_APP | SMTP | Webhook | WhatsApp provider adapter
        ↓
 FastAPI /api/v1
        ↓
 React — Safety Events + Monitoreo
```

## Aislamiento de responsabilidades

- FastAPI: API, RBAC, auditoría, configuración y gestión humana.
- camera-worker: adquisición de video.
- vision-engine: inferencia y eventos de cumplimiento.
- alert-worker: SLA, escalamiento y entrega de notificaciones.
- PostgreSQL: estado transaccional y trazabilidad.
- Redis: frames/heartbeats/estado efímero.
- MinIO: evidencia de Safety Events.

## Multi-tenancy

Toda consulta de monitoreo mantiene alcance por `organization_id`; SUPERADMIN conserva alcance global. Políticas, canales, escalaciones y entregas se vinculan a una organización.
