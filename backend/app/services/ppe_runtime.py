import math
from pathlib import Path
import cv2
import numpy as np

SUPPORTED_PPE = ('HELMET','VEST','SAFETY_SHOES')


def _features(img):
    img=cv2.resize(img,(64,64),interpolation=cv2.INTER_AREA)
    hsv=cv2.cvtColor(img,cv2.COLOR_BGR2HSV)
    h,s,v=cv2.split(hsv)
    hh=cv2.calcHist([hsv],[0],None,[8],[0,180]).flatten(); hh/=max(hh.sum(),1)
    sh=cv2.calcHist([hsv],[1],None,[4],[0,256]).flatten(); sh/=max(sh.sum(),1)
    vh=cv2.calcHist([hsv],[2],None,[4],[0,256]).flatten(); vh/=max(vh.sum(),1)
    ranges=[((18,80,100),(38,255,255)),((4,90,90),(18,255,255)),((38,70,80),(90,255,255)),((90,70,70),(135,255,255)),((0,0,180),(180,70,255)),((0,0,0),(180,255,75)),((5,40,25),(25,220,170))]
    ratios=[float(np.mean(cv2.inRange(hsv,lo,hi)>0)) for lo,hi in ranges]
    edges=cv2.Canny(img,60,160)
    extra=[float(np.mean(edges>0)),float(s.mean()/255),float(v.mean()/255),float(np.std(v)/128)]
    return np.array([[*hh,*sh,*vh,*ratios,*extra]],np.float32)


def body_regions(bbox):
    x,y,w,h=[float(v) for v in bbox]
    return {
        'HELMET':[x+.16*w,y-.01*h,.68*w,.30*h],
        'VEST':[x+.08*w,y+.25*h,.84*w,.45*h],
        'SAFETY_SHOES':[x+.04*w,y+.78*h,.92*w,.24*h],
    }


def _crop_with_visibility(frame,rect):
    fh,fw=frame.shape[:2]; x,y,w,h=rect
    expected=max(w*h,1.0)
    x1=max(0,int(round(x))); y1=max(0,int(round(y))); x2=min(fw,int(round(x+w))); y2=min(fh,int(round(y+h)))
    visible=max(0,x2-x1)*max(0,y2-y1)/expected
    if x2<=x1 or y2<=y1: return None,0.0,[x1,y1,0,0]
    return frame[y1:y2,x1:x2],float(min(1,visible)),[x1,y1,x2-x1,y2-y1]


class OpenCVSVMPPEDetector:
    code='PPE_REGION_SVM_BASELINE'
    backend='opencv_svm_regions'
    def __init__(self, model_dir=None):
        root=Path(model_dir or Path(__file__).resolve().parents[2]/'models'/'ppe')
        self.models={
            'HELMET':cv2.ml.SVM_load(str(root/'helmet_svm.xml')),
            'VEST':cv2.ml.SVM_load(str(root/'vest_svm.xml')),
            'SAFETY_SHOES':cv2.ml.SVM_load(str(root/'shoes_svm.xml')),
        }
    def classify_region(self,code,patch):
        feat=_features(patch)
        _,label=self.models[code].predict(feat)
        _,raw=self.models[code].predict(feat,flags=cv2.ml.STAT_MODEL_RAW_OUTPUT)
        positive=float(label[0,0])>0
        margin=abs(float(raw[0,0])); confidence=0.5+0.5*(1-math.exp(-margin))
        # Domain gates reduce obvious color-confusion errors of the synthetic commissioning model.
        hsv=cv2.cvtColor(cv2.resize(patch,(64,64)),cv2.COLOR_BGR2HSV)
        def ratio(lo,hi): return float(np.mean(cv2.inRange(hsv,lo,hi)>0))
        yellow=ratio((18,80,100),(38,255,255)); orange=ratio((4,90,90),(18,255,255)); green=ratio((38,70,80),(90,255,255)); blue=ratio((90,70,70),(135,255,255)); dark=ratio((0,0,0),(180,255,75)); brown=ratio((5,40,25),(25,220,170))
        if code=='HELMET': positive = positive and ((yellow+green+blue)>=.055 or orange>=.15)
        elif code=='VEST': positive = positive and ((yellow+green)>=.055 or (orange>=.25 and yellow>=.025))
        elif code=='SAFETY_SHOES': positive = positive and ((dark+brown)>=.18)
        # confidence exposed to the API is confidence of EPP presence, not certainty of a negative SVM class.
        confidence = confidence if positive else min(.49, 1.0-confidence)
        return bool(positive),float(min(.995,max(.005,confidence)))
    def inspect_track(self,frame,bbox,thresholds=None,visibility_ratio=.70,uncertainty_margin=.08):
        thresholds=thresholds or {'HELMET':.70,'VEST':.70,'SAFETY_SHOES':.70}
        regions=body_regions(bbox); out={}
        fh,fw=frame.shape[:2]
        track_bottom=float(bbox[1]+bbox[3])
        for code,rect in regions.items():
            patch,visible,clipped=_crop_with_visibility(frame,rect)
            if code=='SAFETY_SHOES' and track_bottom >= fh*.985:
                visible=min(visible,.45)
            if patch is None or visible<float(visibility_ratio) or patch.shape[0]<12 or patch.shape[1]<12:
                out[code]={'status':'NO_VISIBLE','confidence':None,'visible_ratio':round(visible,3),'region_bbox':clipped,'detected':False}
                continue
            positive,confidence=self.classify_region(code,patch)
            threshold=float(thresholds.get(code,.70))
            if abs(confidence-threshold)<=float(uncertainty_margin): status='INCIERTO'
            elif positive and confidence>=threshold: status='OK'
            elif positive: status='INCIERTO'
            else: status='NO_DETECTADO'
            out[code]={'status':status,'confidence':round(confidence,4),'visible_ratio':round(visible,3),'region_bbox':clipped,'detected':bool(positive)}
        return out


def create_ppe_detector(backend, model_metadata=None, artifact_uri=None):
    if backend=='opencv_svm_regions': return OpenCVSVMPPEDetector()
    if backend=='openvino_ir_ppe': return IntelWorkerSafetyPPEDetector(model_metadata, artifact_uri)
    if backend=='onnx_yolox_ppe': return YOLOXONNXPPEDetector(model_metadata, artifact_uri)
    raise RuntimeError(f'Backend EPP no soportado: {backend}')


def render_ppe_overlay(frame, track_items, zones):
    img=frame.copy(); fh,fw=img.shape[:2]
    # zones first
    for zone in zones:
        pts=np.array([[int(p['x']*fw),int(p['y']*fh)] for p in zone.polygon_points],np.int32)
        if len(pts)>=3:
            cv2.polylines(img,[pts],True,(70,210,170),2,cv2.LINE_AA)
            x,y=pts[0]; cv2.putText(img,zone.code,(max(2,x),max(18,y-5)),cv2.FONT_HERSHEY_SIMPLEX,.48,(70,210,170),1,cv2.LINE_AA)
    palette={'OK':(70,220,150),'NO_DETECTADO':(70,80,235),'INCIERTO':(40,190,235),'NO_VISIBLE':(145,145,145)}
    for item in track_items:
        x,y,w,h=[int(round(v)) for v in item['bbox']]
        cv2.rectangle(img,(x,y),(x+w,y+h),(80,220,180),2)
        label=f"{item['track_id']} PERSON {int(item['confidence']*100)}%"
        cv2.putText(img,label,(max(2,x),max(20,y-7)),cv2.FONT_HERSHEY_SIMPLEX,.5,(80,220,180),2,cv2.LINE_AA)
        for code,status in (item.get('ppe') or {}).items():
            bx,by,bw,bh=status.get('region_bbox') or [0,0,0,0]
            color=palette.get(status.get('status'),(180,180,180))
            if bw>0 and bh>0:
                cv2.rectangle(img,(int(bx),int(by)),(int(bx+bw),int(by+bh)),color,1)
                txt=f"{code}: {status.get('status')}"
                cv2.putText(img,txt,(max(2,int(bx)),max(16,int(by)+14)),cv2.FONT_HERSHEY_SIMPLEX,.38,color,1,cv2.LINE_AA)
    ok,jpg=cv2.imencode('.jpg',img,[int(cv2.IMWRITE_JPEG_QUALITY),84])
    return jpg.tobytes() if ok else None

# ---------------------------------------------------------------------------
# v1.0.0 real/trainable PPE backends
# ---------------------------------------------------------------------------
import os
import xml.etree.ElementTree as ET
from functools import lru_cache


def _resolve_artifact(artifact_uri=None, default_rel=None):
    from app.core.config import settings
    root = Path(settings.hys_model_root)
    rel = artifact_uri or default_rel
    if not rel:
        return None
    p = Path(rel)
    if not p.is_absolute():
        p = root / rel
    return p


def _ir_input_size(xml_path: Path, fallback=(600, 600)):
    """Read NCHW input size from an OpenVINO IR XML without importing OpenVINO."""
    try:
        tree = ET.parse(xml_path)
        for layer in tree.getroot().iter('layer'):
            if layer.attrib.get('type') in {'Parameter', 'Input'}:
                dims = [int(x.text) for x in layer.iter('dim') if x.text and x.text.isdigit()]
                if len(dims) >= 4:
                    return int(dims[-1]), int(dims[-2])
    except Exception:
        pass
    return fallback


def _standard_detection_rows(outputs):
    """Normalize common SSD DetectionOutput tensors to N x 7 rows."""
    arrays = outputs if isinstance(outputs, (list, tuple)) else [outputs]
    for arr in arrays:
        a = np.asarray(arr)
        if a.size and a.ndim >= 1 and a.shape[-1] == 7:
            return a.reshape(-1, 7)
    return np.empty((0, 7), dtype=np.float32)


def _ov_port_name(port):
    """Best-effort stable OpenVINO output name for diagnostics/parser selection."""
    for attr in ('get_any_name', 'any_name'):
        try:
            value = getattr(port, attr)
            value = value() if callable(value) else value
            if value:
                return str(value)
        except Exception:
            pass
    try:
        names = sorted(str(x) for x in port.get_names())
        if names:
            return names[0]
    except Exception:
        pass
    return ''


def _geti_boxes_labels(named_outputs):
    """Normalize Geti/OTX two-output detector tensors.

    Common exported Geti detectors expose ``boxes`` (N x 5: x1,y1,x2,y2,score)
    and ``labels`` (N).  The helper also falls back to shape/dtype inference so it
    remains usable when graph output names change between OpenVINO releases.
    Returns tuples ``(label, score, x1, y1, x2, y2)``.
    """
    if not named_outputs:
        return []
    items=[(str(name or '').lower(), np.asarray(arr)) for name,arr in named_outputs]
    boxes=None; labels=None
    for name,a in items:
        if 'box' in name and a.size and a.ndim>=1 and a.shape[-1] in (4,5):
            boxes=a
        elif 'label' in name and a.size:
            labels=a
    if boxes is None:
        for _,a in items:
            if a.size and a.ndim>=1 and a.shape[-1] in (4,5):
                boxes=a; break
    if labels is None:
        for _,a in items:
            if a is boxes or not a.size:
                continue
            flat=a.reshape(-1)
            # Labels are integer-like; this avoids mistaking a score tensor for labels.
            if flat.size and np.all(np.isfinite(flat)) and np.mean(np.abs(flat-np.round(flat))<1e-4) >= .95:
                labels=a; break
    if boxes is None or labels is None:
        return []
    b=np.asarray(boxes).reshape(-1, boxes.shape[-1])
    lab=np.asarray(labels).reshape(-1)
    n=min(len(b), len(lab))
    out=[]
    for i in range(n):
        label=float(lab[i])
        row=[float(x) for x in b[i]]
        if len(row)==5:
            x1,y1,x2,y2,score=row
        else:
            # Four-coordinate outputs do not carry confidence. They are not safe for
            # compliance decisions, so keep a neutral score that will be filtered.
            x1,y1,x2,y2=row; score=0.0
        if not np.isfinite([label,score,x1,y1,x2,y2]).all():
            continue
        out.append((label,score,x1,y1,x2,y2))
    return out


class IntelWorkerSafetyPPEDetector:
    """MIT licensed Intel/Geti bootstrap detector for real helmet + vest video.

    The model artifact itself is downloaded separately from Intel Edge AI Resources.
    It is used as a bootstrap detector so HYS can work on real footage immediately,
    while the HYS-owned YOLOX/ONNX model is trained and evaluated.
    """
    code = 'INTEL_WORKER_SAFETY_BOOTSTRAP'
    backend = 'openvino_ir_ppe'
    supported_codes = ('HELMET', 'VEST')

    def __init__(self, model_metadata=None, artifact_uri=None):
        meta = model_metadata or {}
        xml_path = _resolve_artifact(artifact_uri, 'bootstrap/intel-worker-safety/model.xml')
        if not xml_path or not xml_path.exists():
            raise RuntimeError(f'Modelo Intel Worker Safety no instalado: {xml_path}')
        bin_path = xml_path.with_suffix('.bin')
        if not bin_path.exists():
            raise RuntimeError(f'BIN OpenVINO ausente: {bin_path}')
        self.xml_path = xml_path
        self.bin_path = bin_path
        # OpenCV's PyPI wheels do not ship the OpenVINO DNN plugin required to
        # execute IR (.xml/.bin) networks. Use Intel's Apache-2.0 OpenVINO
        # Runtime directly instead of cv2.dnn.readNet().
        try:
            import openvino as ov
        except Exception as exc:
            raise RuntimeError(
                'OpenVINO Runtime no instalado. Instale el paquete openvino del runtime HYS.'
            ) from exc
        self.ov = ov
        self.core = ov.Core()
        try:
            model = self.core.read_model(model=str(xml_path), weights=str(bin_path))
            self.compiled_model = self.core.compile_model(model, 'CPU')
        except Exception as exc:
            raise RuntimeError(f'No se pudo compilar modelo Intel Worker Safety con OpenVINO Runtime: {exc}') from exc
        self.input_port = self.compiled_model.input(0)
        self.output_ports = list(self.compiled_model.outputs)
        port_shape = []
        try:
            port_shape = [int(v) for v in self.input_port.shape]
        except Exception:
            port_shape = []
        derived = None
        self.input_layout = 'NCHW'
        if len(port_shape) == 4:
            if port_shape[1] in (1, 3, 4):
                derived = (port_shape[3], port_shape[2])
                self.input_layout = 'NCHW'
            elif port_shape[3] in (1, 3, 4):
                derived = (port_shape[2], port_shape[1])
                self.input_layout = 'NHWC'
        # The compiled graph is authoritative. Registry metadata can be stale (the
        # bootstrap was initially registered as 600x600 while the pinned graph is 640x640).
        self.input_size = tuple(derived or meta.get('input_size') or _ir_input_size(xml_path))
        self.registry_input_size = tuple(meta.get('input_size') or ())
        self.threshold = float(meta.get('default_threshold', 0.40))
        self.class_thresholds = {'HELMET': float(meta.get('helmet_threshold', 0.57)), 'VEST': float(meta.get('vest_threshold', 0.525))}
        # Intel's pinned Worker Safety sample uses DetectionOutput: 1=helmet, 2=safety_jacket.
        self.label_map = {1: 'HELMET', 2: 'VEST'}
        custom = meta.get('detection_output_label_map') or {}
        for k, v in custom.items():
            self.label_map[int(k)] = str(v)
        # Geti/OTX boxes+labels exports use zero-based class indices. Intel's
        # Worker Safety model card declares 0=safety_jacket, 1=safety_helmet.
        self.geti_label_map = {0: 'VEST', 1: 'HELMET'}

    def _detect_crop(self, crop, threshold=None):
        if crop is None or crop.size == 0:
            return []
        iw, ih = self.input_size
        resized = cv2.resize(crop, (int(iw), int(ih)), interpolation=cv2.INTER_LINEAR)
        tensor = resized.astype(np.float32, copy=False)
        if getattr(self, 'input_layout', 'NCHW') == 'NCHW':
            tensor = tensor.transpose(2, 0, 1)[None, ...]
        else:
            tensor = tensor[None, ...]
        tensor = np.ascontiguousarray(tensor)
        try:
            result = self.compiled_model([tensor])
        except Exception:
            # Mapping by input port is supported across OpenVINO 2025/2026 and
            # is a safe fallback for models whose input cannot be inferred from
            # positional dispatch.
            result = self.compiled_model({self.input_port: tensor})
        named = [(_ov_port_name(p), np.asarray(result[p])) for p in self.output_ports]
        raw = [arr for _,arr in named]
        rows = _standard_detection_rows(raw)
        h, w = crop.shape[:2]
        detections = []
        base_thr = float(self.threshold if threshold is None else threshold)

        def append_detection(code, conf, x1, y1, x2, y2):
            if not code:
                return
            class_thr = max(base_thr, float(self.class_thresholds.get(code, base_thr)))
            if float(conf) < class_thr:
                return
            coords=[float(x1),float(y1),float(x2),float(y2)]
            if max(abs(v) for v in coords) <= 2.0:
                bx1, by1, bx2, by2 = coords[0]*w, coords[1]*h, coords[2]*w, coords[3]*h
            else:
                # Geti boxes are commonly expressed in model-input pixels. Scale them
                # back to the original crop instead of drawing 640-space coordinates.
                iw, ih = self.input_size
                sx, sy = w / max(float(iw),1.0), h / max(float(ih),1.0)
                bx1, by1, bx2, by2 = coords[0]*sx, coords[1]*sy, coords[2]*sx, coords[3]*sy
            bx1=max(0.0,min(float(w),bx1)); by1=max(0.0,min(float(h),by1))
            bx2=max(0.0,min(float(w),bx2)); by2=max(0.0,min(float(h),by2))
            bw, bh = max(0.0,bx2-bx1), max(0.0,by2-by1)
            if bw < 2 or bh < 2:
                return
            detections.append({'code':code,'confidence':float(conf),'bbox':[bx1,by1,bw,bh]})

        if len(rows):
            # Legacy/SSD DetectionOutput path (one-based label IDs, background=0).
            for row in rows:
                image_id,label,conf,x1,y1,x2,y2=[float(x) for x in row]
                if image_id < -0.5:
                    continue
                append_detection(self.label_map.get(int(round(label))), conf, x1,y1,x2,y2)
        else:
            # Current Geti export path: separate boxes + labels outputs.
            for label,conf,x1,y1,x2,y2 in _geti_boxes_labels(named):
                append_detection(self.geti_label_map.get(int(round(label))), conf, x1,y1,x2,y2)
        return detections

    def inspect_track(self, frame, bbox, thresholds=None, visibility_ratio=.70, uncertainty_margin=.08):
        thresholds = thresholds or {'HELMET': .70, 'VEST': .70, 'SAFETY_SHOES': .70}
        fh, fw = frame.shape[:2]
        x, y, w, h = [float(v) for v in bbox]
        x1, y1 = max(0, int(x)), max(0, int(y))
        x2, y2 = min(fw, int(x+w)), min(fh, int(y+h))
        if x2 <= x1 or y2 <= y1:
            return {k: {'status':'NO_VISIBLE','confidence':None,'visible_ratio':0.0,'region_bbox':[0,0,0,0],'detected':False} for k in SUPPORTED_PPE}
        person = frame[y1:y2, x1:x2]
        detections = self._detect_crop(person, threshold=min(float(thresholds.get('HELMET', .7)), float(thresholds.get('VEST', .7)), .40))
        regions = body_regions(bbox)
        out = {}
        for code in ('HELMET', 'VEST'):
            patch, visible, clipped = _crop_with_visibility(frame, regions[code])
            if patch is None or visible < float(visibility_ratio):
                out[code] = {'status':'NO_VISIBLE','confidence':None,'visible_ratio':round(visible,3),'region_bbox':clipped,'detected':False,'provider':'intel-worker-safety'}
                continue
            best = 0.0
            for d in detections:
                if d['code'] != code:
                    continue
                dx, dy, dw, dh = d['bbox']
                cx, cy = dx + dw/2.0, dy + dh/2.0
                # Anatomical gate inside the person crop.
                if code == 'HELMET' and cy > person.shape[0] * .48:
                    continue
                if code == 'VEST' and not (person.shape[0] * .18 <= cy <= person.shape[0] * .78):
                    continue
                best = max(best, float(d['confidence']))
            threshold = float(thresholds.get(code, .70))
            if best >= threshold:
                status = 'OK'
            elif best > 0 and abs(best-threshold) <= float(uncertainty_margin):
                status = 'INCIERTO'
            elif best > 0:
                status = 'INCIERTO'
            else:
                status = 'NO_DETECTADO'
            out[code] = {'status':status,'confidence':round(best,4) if best else 0.0,'visible_ratio':round(visible,3),'region_bbox':clipped,'detected':best>=threshold,'provider':'intel-worker-safety'}

        # Intel bootstrap does not claim footwear capability. Never infer a violation.
        patch, visible, clipped = _crop_with_visibility(frame, regions['SAFETY_SHOES'])
        if patch is None or visible < float(visibility_ratio) or (y+h) >= fh*.985:
            status = 'NO_VISIBLE'
        else:
            status = 'INCIERTO'
        out['SAFETY_SHOES'] = {'status':status,'confidence':None,'visible_ratio':round(visible,3),'region_bbox':clipped,'detected':False,'provider':'intel-worker-safety','reason':'MODEL_UNSUPPORTED'}
        return out


def _yolox_preprocess(img, input_size):
    if img is None or img.size == 0:
        raise ValueError('imagen vacia')
    ih, iw = input_size
    h, w = img.shape[:2]
    ratio = min(ih / max(h,1), iw / max(w,1))
    resized = cv2.resize(img, (int(w*ratio), int(h*ratio)), interpolation=cv2.INTER_LINEAR)
    padded = np.full((ih, iw, 3), 114, dtype=np.uint8)
    padded[:resized.shape[0], :resized.shape[1]] = resized
    tensor = padded.transpose(2,0,1).astype(np.float32)[None, ...]
    return tensor, ratio


def _yolox_demo_postprocess(outputs, img_size, p6=False):
    grids, expanded_strides = [], []
    strides = [8,16,32] + ([64] if p6 else [])
    for stride in strides:
        hsize, wsize = img_size[0] // stride, img_size[1] // stride
        xv, yv = np.meshgrid(np.arange(wsize), np.arange(hsize))
        grid = np.stack((xv, yv), 2).reshape(1, -1, 2)
        grids.append(grid)
        expanded_strides.append(np.full((*grid.shape[:2],1), stride))
    grids = np.concatenate(grids,1)
    expanded_strides = np.concatenate(expanded_strides,1)
    out = outputs.copy()
    if out.shape[1] == grids.shape[1]:
        out[..., :2] = (out[..., :2] + grids) * expanded_strides
        out[..., 2:4] = np.exp(out[..., 2:4]) * expanded_strides
    return out


def _xywh_to_xyxy(boxes):
    out = boxes.copy()
    out[:,0] = boxes[:,0] - boxes[:,2]/2
    out[:,1] = boxes[:,1] - boxes[:,3]/2
    out[:,2] = boxes[:,0] + boxes[:,2]/2
    out[:,3] = boxes[:,1] + boxes[:,3]/2
    return out


class YOLOXONNXPPEDetector:
    code = 'HYS_PPE_YOLOX_ONNX'
    backend = 'onnx_yolox_ppe'

    def __init__(self, model_metadata=None, artifact_uri=None):
        try:
            import onnxruntime as ort
        except Exception as exc:
            raise RuntimeError('onnxruntime no instalado') from exc
        meta = model_metadata or {}
        path = _resolve_artifact(artifact_uri)
        if not path or not path.exists():
            raise RuntimeError(f'ONNX PPE no encontrado: {path}')
        self.path = path
        self.session = ort.InferenceSession(str(path), providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = (int(meta.get('input_height',640)), int(meta.get('input_width',640)))
        self.class_map = {int(k):str(v) for k,v in (meta.get('class_map') or {}).items()}
        self.conf_threshold = float(meta.get('default_threshold', .35))
        self.nms_threshold = float(meta.get('nms_threshold', .45))
        self.decode_grid = bool(meta.get('decode_grid', True))
        self.p6 = bool(meta.get('p6', False))

    def _detect_crop(self, crop):
        tensor, ratio = _yolox_preprocess(crop, self.input_size)
        raw = self.session.run(None, {self.input_name:tensor})[0]
        outputs = _yolox_demo_postprocess(raw, self.input_size, self.p6) if self.decode_grid else raw
        pred = outputs[0]
        if pred.ndim != 2 or pred.shape[1] < 6:
            return []
        boxes = _xywh_to_xyxy(pred[:,:4]) / max(ratio,1e-9)
        obj = pred[:,4]
        cls_probs = pred[:,5:]
        cls_ids = np.argmax(cls_probs, axis=1)
        scores = obj * cls_probs[np.arange(len(cls_probs)), cls_ids]
        out=[]
        for cls in np.unique(cls_ids):
            idx=np.where((cls_ids==cls)&(scores>=self.conf_threshold))[0]
            if not len(idx): continue
            b=boxes[idx]; sc=scores[idx]
            nms_boxes=[[int(x1),int(y1),int(max(1,x2-x1)),int(max(1,y2-y1))] for x1,y1,x2,y2 in b]
            keep=cv2.dnn.NMSBoxes(nms_boxes,sc.tolist(),self.conf_threshold,self.nms_threshold)
            for j in np.array(keep).reshape(-1) if len(keep) else []:
                i=idx[int(j)]; code=self.class_map.get(int(cls_ids[i]))
                if not code: continue
                x1,y1,x2,y2=boxes[i]
                out.append({'code':code,'confidence':float(scores[i]),'bbox':[float(x1),float(y1),float(x2-x1),float(y2-y1)]})
        return out

    def inspect_track(self, frame, bbox, thresholds=None, visibility_ratio=.70, uncertainty_margin=.08):
        thresholds=thresholds or {'HELMET':.70,'VEST':.70,'SAFETY_SHOES':.70}
        fh,fw=frame.shape[:2]; x,y,w,h=[float(v) for v in bbox]
        x1,y1=max(0,int(x)),max(0,int(y)); x2,y2=min(fw,int(x+w)),min(fh,int(y+h))
        if x2<=x1 or y2<=y1:
            return {k:{'status':'NO_VISIBLE','confidence':None,'visible_ratio':0.0,'region_bbox':[0,0,0,0],'detected':False} for k in SUPPORTED_PPE}
        crop=frame[y1:y2,x1:x2]
        detections=self._detect_crop(crop)
        regions=body_regions(bbox); out={}
        for code in SUPPORTED_PPE:
            patch,visible,clipped=_crop_with_visibility(frame,regions[code])
            if code=='SAFETY_SHOES' and (y+h)>=fh*.985: visible=min(visible,.45)
            if patch is None or visible<float(visibility_ratio):
                out[code]={'status':'NO_VISIBLE','confidence':None,'visible_ratio':round(visible,3),'region_bbox':clipped,'detected':False,'provider':'hys-yolox-onnx'}; continue
            best=0.0
            for d in detections:
                if d['code']!=code: continue
                dx,dy,dw,dh=d['bbox']; cy=dy+dh/2.0
                if code=='HELMET' and cy>crop.shape[0]*.48: continue
                if code=='VEST' and not(crop.shape[0]*.18<=cy<=crop.shape[0]*.80): continue
                if code=='SAFETY_SHOES' and cy<crop.shape[0]*.62: continue
                best=max(best,float(d['confidence']))
            threshold=float(thresholds.get(code,.70))
            if best>=threshold: status='OK'
            elif best>0: status='INCIERTO'
            else: status='NO_DETECTADO'
            out[code]={'status':status,'confidence':round(best,4) if best else 0.0,'visible_ratio':round(visible,3),'region_bbox':clipped,'detected':best>=threshold,'provider':'hys-yolox-onnx'}
        return out
