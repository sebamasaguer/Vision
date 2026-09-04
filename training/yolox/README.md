# HYS PPE Training - YOLOX 0.3.0

YOLOX is fetched from the official `Megvii-BaseDetection/YOLOX` tag `0.3.0` and is Apache-2.0.
This training container does not install or use Ultralytics.

Full training requires an NVIDIA CUDA runtime. The exported `.onnx` runs in HYS Vision IA through ONNX Runtime CPU.
Dataset input must be COCO-format and HYS-owned/permissively licensed.
