FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime
ARG YOLOX_REF=0.3.0
RUN apt-get update && apt-get install -y --no-install-recommends git gcc g++ libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch ${YOLOX_REF} https://github.com/Megvii-BaseDetection/YOLOX.git /opt/YOLOX
WORKDIR /opt/YOLOX
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -v -e . && pip install --no-cache-dir onnx==1.17.0 onnxsim==0.4.36 pycocotools
COPY . /workspace
ENV PYTHONPATH=/opt/YOLOX:/workspace
ENTRYPOINT ["python","/workspace/train_and_export.py"]
