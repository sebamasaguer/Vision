# Bloque 3 — Visión Artificial Base v0.4.0

## Objetivo

Introduce detección **real** de clase `PERSON`, tracking temporal anónimo `TRACK-XXXX`, asignación a polígonos normalizados del Bloque 2 y overlay en tiempo real.

No se implementa todavía detección de EPP. El motor no identifica personas ni usa reconocimiento facial.

## Pipeline

`camera-worker -> Redis frame -> vision-engine -> detector PERSON -> IoU tracker -> zone mapping -> Redis runtime/overlay -> FastAPI -> React`

## Detector baseline

- Backend: OpenCV HOG + SVM default people detector.
- Clase: PERSON.
- Ejecución: CPU.
- Licencia declarada: Apache-2.0.
- Uso comercial: permitido por OpenCV.
- No se descargan pesos de terceros durante la instalación.

El detector está detrás de `create_detector(backend)`. La base de datos registra el backend/version/licencia y `CameraVisionSetting` referencia el modelo. Un backend ONNX/TensorRT/DeepStream puede sustituirlo sin alterar tracking, zonas ni API.

## Tracking

Tracker IoU temporal por cámara:

- IDs anónimos `TRACK-0001`, `TRACK-0002`, ...
- `tracker_iou_threshold` configurable.
- `tracker_max_missed_frames` configurable.
- No persiste identidad biométrica.
- Si el motor reinicia, los IDs temporales se reinician por diseño.

## Zone mapping

Para cada track se usa el punto de apoyo del bounding box (`centro X`, `borde inferior Y`) y se evalúa `point-in-polygon` contra las zonas activas de la cámara.

## Redis

- `hys:vision-engine:heartbeat`
- `hys:vision:result:<camera_id>`
- `hys:vision:overlay:<camera_id>`

Los resultados son efímeros. Los eventos persistentes se implementan en el Bloque 5.

## API

- `GET /api/v1/vision/worker`
- `GET /api/v1/vision/cameras`
- `GET/PATCH /api/v1/vision/cameras/{id}/settings`
- `GET /api/v1/vision/cameras/{id}/runtime`
- `GET /api/v1/vision/cameras/{id}/overlay.jpg`

## Demo y certificación positiva

`demo/demo_camera.mp4` se conserva como fuente geométrica para certificar ingestión y tiempo real; no contiene una persona fotográfica, por lo que puede mostrar `PERSONAS = 0`.

El Bloque 3 incluye además `demo/person_demo_pd.mp4`, un clip QA de 10 segundos derivado de `skimage.data.astronaut`. La documentación de scikit-image declara esa imagen sin restricciones conocidas y liberada al dominio público. El instalador no reemplaza automáticamente la Demo Camera existente.

Para una prueba visual positiva ejecute:

```powershell
.\scripts\usar_demo_personas_incluido.ps1
```

También puede usar `scripts/cargar_video_demo_personas.ps1 -VideoPath <mp4>` con un video propio/autorizado.

## Hotfix v0.4.1 — Person Detector Hardening

El pipeline PERSON ahora separa propuestas crudas de personas confirmadas. Antes de tracking aplica clipping, filtros geométricos y NMS. El tracker requiere persistencia temporal (`candidate -> confirmed`) y sólo los tracks confirmados se publican como personas o se dibujan en el overlay.

QA de referencia incluido:
- escena geométrica: 0 PERSON / 0 TRACKS confirmados;
- clip con persona: TRACK confirmado y estable.
