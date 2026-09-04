# Bloque 7 v0.8.0 — Alertas, SLA, Escalamiento y Monitoreo

## Flujo

```text
Safety Event confirmado
        ↓
Prioridad por severidad
        ↓
SLA ACK + SLA Resolución
        ↓
alert-worker
        ↓
Vencimiento / Breach
        ↓
Escalamiento L1..Ln
        ↓
IN_APP / EMAIL / WEBHOOK / WHATSAPP
        ↓
Bandeja de Monitoreo
```

## SLA iniciales

| Severidad | Prioridad | ACK | Resolución | 1er escalamiento | Repetición | Máx. nivel |
|---|---|---:|---:|---:|---:|---:|
| ADVERTENCIA | P2_ADVERTENCIA | 300 s | 1800 s | 300 s | 300 s | 2 |
| ALTA | P1_ALTA | 120 s | 900 s | 120 s | 180 s | 3 |
| CRITICA | P0_CRITICA | 60 s | 600 s | 60 s | 120 s | 4 |

Las políticas son configurables por organización desde la pestaña **SLA y Escalamiento**.

## Estados SLA

- `PENDING`: todavía dentro del plazo.
- `MET`: acción cumplida dentro del SLA.
- `BREACHED`: vencimiento superado.

El reconocimiento y la resolución operativa del Bloque 6 actualizan el SLA de manera inmediata.

## Escalamiento

Cada Safety Event mantiene un `escalation_level`. El `alert-worker` sólo crea un registro por `evento + nivel`, evitando duplicados. Cuando llega al máximo configurado, `next_escalation_at` queda en `NULL`.

Los eventos heredados del Bloque 6 reciben una nueva ventana SLA desde la activación del Bloque 7; no se retroactivan vencimientos históricos y se evita una tormenta de alertas al migrar.

## Notificaciones

- `IN_APP`: activa siempre; materializa la alerta en la bandeja.
- `EMAIL`: SMTP configurable por `.env` + destinatario por organización.
- `WEBHOOK`: POST JSON a URL configurable; token bearer opcional en `.env`.
- `WHATSAPP`: adaptador genérico a webhook de proveedor; número/destino en la organización y credenciales en `.env`.

La base de datos registra entregas, intentos, estado, error y referencia externa. No guarda passwords ni tokens de proveedores.

## Bandeja de Monitoreo

Prioriza eventos por:

1. resolución vencida;
2. ACK vencido;
3. prioridad P0 → P3;
4. nivel de escalamiento;
5. antigüedad.

Filtros: severidad, estado SLA y "asignados a mí". La pantalla incluye resumen ejecutivo operativo, configuración de SLA/canales y entregas recientes.
