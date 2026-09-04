# Bloque 2 v0.3.0 — Zonas + EPP + reglas

## Entidades

- `ppe_types`: catálogo administrable, detector class y confidence mínimo.
- `zones`: polígono por cámara en coordenadas normalizadas `0..1`.
- `zone_ppe_rules`: relación dinámica zona/EPP con obligatoriedad, criticidad y contexto.

## API

- `GET/POST/PATCH/DELETE /api/v1/ppe`
- `GET/POST/PATCH/DELETE /api/v1/zones`
- `GET/PUT /api/v1/zones/{id}/rules`

## Editor

La pantalla **Zonas y EPP** obtiene una captura real de la cámara, dibuja el polígono en SVG y guarda cada punto como `{x,y}` normalizado. Los vértices pueden arrastrarse para corregir la geometría sin depender de la resolución original.

## Reglas

Cada EPP puede configurarse como `REQUIRED` u `OPTIONAL`, con severidad `INFO`, `ADVERTENCIA`, `ALTA` o `CRITICA`, confidence específico y contexto opcional de horario, tarea, riesgo y operación. En este bloque las reglas se configuran; todavía no se evalúan contra inferencias IA.
