# Bloque 10 — Dataset Manager Visual

Pipeline operativo:

`Cámara / Video -> Frames -> SHA-256 -> Curación -> Bounding Boxes -> Ground Truth -> Freeze COCO -> Training -> Evaluación -> SHADOW -> Promoción controlada`.

La captura de cámara reutiliza el último JPEG publicado por `camera-worker` en Redis. La captura de video usa OpenCV y muestreo temporal para evitar almacenar todos los frames consecutivos. La deduplicación exacta se realiza por SHA-256 y los duplicados quedan marcados sin ingresar automáticamente al dataset de entrenamiento.

La evaluación de Ground Truth compara detecciones PPE mediante IoU configurable. La promoción a producción es un endpoint separado y exige `confirm=true`, métricas mínimas y suficiente evidencia SHADOW por cámara.
