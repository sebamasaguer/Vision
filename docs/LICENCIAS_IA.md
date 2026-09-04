# Licencias IA — HYS Vision IA

## PERSON
- OpenCV HOG default people detector.
- OpenCV: Apache-2.0.
- Baseline CPU reemplazable.

## PPE v0.5.0
- Código de inferencia: proyecto HYS Vision IA sobre OpenCV.
- Backend: `opencv_svm_regions`.
- Pesos `helmet_svm.xml`, `vest_svm.xml`, `shoes_svm.xml`: generados dentro del proyecto a partir de datos sintéticos generados por el propio build.
- No se incorporan pesos Ultralytics/YOLO ni datasets externos silenciosamente.
- Uso: baseline de commissioning/QA. `production_certified=false` en metadata.
- Para producción: incorporar un modelo PPE con licencia, dataset, métricas y validación explícitas mediante el proveedor desacoplado.


## Bloque 9 v1.0.0
- Ultralytics: **no usado** en entrenamiento ni runtime.
- Training stack HYS: YOLOX 0.3.0, Apache-2.0.
- Runtime del modelo HYS: ONNX Runtime.
- Bootstrap para prueba real inmediata: Intel Worker Safety Gear Detection, descargado desde fuente oficial fijada por commit y registrado con SHA-256/provenance. Se usa sólo para HELMET/VEST y SHADOW/puesta en marcha.
- SAFETY_SHOES no se infiere por ausencia cuando el bootstrap no lo soporta.
- El modelo HYS propio debe entrenarse con dataset HYS y pasar test independiente + SHADOW antes de promoción a PRODUCTION.
