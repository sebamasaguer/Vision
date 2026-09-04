# Bloque 4 v0.5.0 — IA EPP por TRACK

Flujo implementado:

`PERSON -> TRACK confirmado -> regiones anatómicas -> HELMET/VEST/SAFETY_SHOES -> asociación al mismo TRACK -> OK/NO_DETECTADO/INCIERTO/NO_VISIBLE`.

## Baseline ML incluido

`PPE_REGION_SVM_BASELINE` usa tres SVM de OpenCV sobre features de color/textura de regiones de cabeza, torso y pies. Los modelos fueron entrenados con datos sintéticos generados dentro del proyecto; no se incluyen pesos de terceros. Es un baseline de puesta en marcha y QA, no una certificación de precisión industrial. Antes de producción debe calibrarse/validarse con cámaras y dataset del cliente o reemplazarse por un proveedor ONNX/TensorRT/DeepStream validado.

## Asociación

El detector EPP nunca busca EPP globalmente en la imagen. Recorta cabeza/torso/pies de cada `TRACK-XXXX` confirmado y devuelve el EPP dentro de ese track. Esto reduce cruces entre personas próximas.

## Estados

- `OK`: detector positivo con confidence suficiente.
- `NO_DETECTADO`: región visible y detector negativo.
- `INCIERTO`: score dentro del margen configurable alrededor del threshold.
- `NO_VISIBLE`: región corporal insuficientemente visible; no equivale a incumplimiento.

No se generan alertas en este bloque. Persistencia temporal, deduplicación y reglas de cumplimiento quedan para Bloque 5.
