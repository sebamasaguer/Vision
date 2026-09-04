import hashlib
import json
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ml import MLDataset, MLDatasetVersion
from app.models.ml_dataset_visual import MLDatasetFrame, MLGroundTruthAnnotation, MLEvaluationRun
from app.models.vision import VisionModelVersion
from app.services.ml_registry import artifact_path
from app.services.ppe_runtime import create_ppe_detector

CLASSES = ('PERSON','HELMET','VEST','SAFETY_SHOES','GLOVES','GOGGLES','HARNESS','WORK_CLOTHING','HIGH_VISIBILITY_CLOTHING')


def utcnow(): return datetime.now(timezone.utc)

def sha_bytes(data: bytes): return hashlib.sha256(data).hexdigest()

def dataset_root(dataset: MLDataset):
    root=Path(settings.hys_dataset_root)/dataset.code
    root.mkdir(parents=True,exist_ok=True)
    return root

def _relative(path: Path):
    root=Path(settings.hys_dataset_root)
    try: return str(path.resolve().relative_to(root.resolve())).replace('\\','/')
    except Exception: return str(path)

def frame_path(frame: MLDatasetFrame):
    p=Path(frame.image_path)
    return p if p.is_absolute() else Path(settings.hys_dataset_root)/p

def serialize_annotation(a: MLGroundTruthAnnotation):
    return {'id':str(a.id),'class_code':a.class_code,'x':a.x,'y':a.y,'width':a.width,'height':a.height,'source':a.source,'verified':a.verified}

def serialize_frame(db: Session, f: MLDatasetFrame, include_annotations=True):
    anns=[]
    if include_annotations:
        anns=[serialize_annotation(a) for a in db.scalars(select(MLGroundTruthAnnotation).where(MLGroundTruthAnnotation.frame_id==f.id).order_by(MLGroundTruthAnnotation.created_at))]
    return {'id':str(f.id),'dataset_id':str(f.dataset_id),'camera_id':str(f.camera_id) if f.camera_id else None,'source_type':f.source_type,'source_ref':f.source_ref,'frame_index':f.frame_index,'captured_at':f.captured_at,'sha256':f.sha256,'width':f.width,'height':f.height,'curation_status':f.curation_status,'ground_truth_status':f.ground_truth_status,'duplicate_of_id':str(f.duplicate_of_id) if f.duplicate_of_id else None,'created_at':f.created_at,'annotations':anns}

def ingest_jpeg(db: Session, dataset: MLDataset, data: bytes, *, camera_id=None, source_type='UPLOAD', source_ref=None, frame_index=None, actor_id=None, dedupe=True):
    img=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR)
    if img is None: raise ValueError('Imagen no decodificable')
    ok,enc=cv2.imencode('.jpg',img,[int(cv2.IMWRITE_JPEG_QUALITY),92])
    if not ok: raise ValueError('No se pudo normalizar JPEG')
    payload=enc.tobytes(); digest=sha_bytes(payload)
    existing=db.scalar(select(MLDatasetFrame).where(MLDatasetFrame.dataset_id==dataset.id,MLDatasetFrame.sha256==digest).limit(1)) if dedupe else None
    fid=uuid.uuid4(); out=dataset_root(dataset)/'working'/'images'/f'{fid}.jpg'; out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(payload)
    h,w=img.shape[:2]
    f=MLDatasetFrame(id=fid,organization_id=dataset.organization_id,dataset_id=dataset.id,camera_id=camera_id,source_type=source_type,source_ref=source_ref,frame_index=frame_index,captured_at=utcnow(),image_path=_relative(out),sha256=digest,width=w,height=h,curation_status='PENDING' if not existing else 'DUPLICATE',ground_truth_status='UNLABELED',duplicate_of_id=existing.id if existing else None,created_by_user_id=actor_id,created_at=utcnow(),updated_at=utcnow())
    db.add(f);db.flush();return f

def ingest_video(db: Session, dataset: MLDataset, video_path: Path, *, every_seconds=1.0, max_frames=120, actor_id=None, source_ref=None):
    cap=cv2.VideoCapture(str(video_path))
    if not cap.isOpened(): raise ValueError('Video no decodificable')
    fps=float(cap.get(cv2.CAP_PROP_FPS) or 25.0); step=max(1,int(round(fps*max(0.1,every_seconds))))
    idx=0; saved=[]
    while len(saved)<max_frames:
        ok,frame=cap.read()
        if not ok: break
        if idx%step==0:
            ok2,enc=cv2.imencode('.jpg',frame,[int(cv2.IMWRITE_JPEG_QUALITY),92])
            if ok2: saved.append(ingest_jpeg(db,dataset,enc.tobytes(),source_type='VIDEO',source_ref=source_ref or video_path.name,frame_index=idx,actor_id=actor_id))
        idx+=1
    cap.release(); return saved

def replace_annotations(db: Session, frame: MLDatasetFrame, annotations: list[dict], verified: bool, actor_id=None):
    db.execute(delete(MLGroundTruthAnnotation).where(MLGroundTruthAnnotation.frame_id==frame.id))
    for item in annotations:
        code=str(item['class_code']).upper().strip()
        if code not in CLASSES: raise ValueError(f'Clase no soportada: {code}')
        x,y,w,h=[float(item[k]) for k in ('x','y','width','height')]
        if min(x,y,w,h)<0 or x+w>1.0001 or y+h>1.0001 or w<=0 or h<=0: raise ValueError('Bounding box normalizado inválido')
        db.add(MLGroundTruthAnnotation(frame_id=frame.id,class_code=code,x=x,y=y,width=w,height=h,source='MANUAL',verified=verified,created_by_user_id=actor_id,created_at=utcnow(),updated_at=utcnow()))
    frame.ground_truth_status='VERIFIED' if verified else ('PARTIAL' if annotations else 'UNLABELED')
    frame.updated_at=utcnow(); db.flush()

def workspace(db: Session, dataset: MLDataset, limit=400):
    rows=list(db.scalars(select(MLDatasetFrame).where(MLDatasetFrame.dataset_id==dataset.id).order_by(MLDatasetFrame.created_at.desc()).limit(limit)))
    stats={}
    for key in ('PENDING','ACCEPTED','REJECTED','DUPLICATE'):
        stats[key]=db.scalar(select(func.count(MLDatasetFrame.id)).where(MLDatasetFrame.dataset_id==dataset.id,MLDatasetFrame.curation_status==key)) or 0
    verified=db.scalar(select(func.count(MLDatasetFrame.id)).where(MLDatasetFrame.dataset_id==dataset.id,MLDatasetFrame.ground_truth_status=='VERIFIED')) or 0
    ann_count=db.scalar(select(func.count(MLGroundTruthAnnotation.id)).join(MLDatasetFrame,MLGroundTruthAnnotation.frame_id==MLDatasetFrame.id).where(MLDatasetFrame.dataset_id==dataset.id)) or 0
    return {'dataset':{'id':str(dataset.id),'code':dataset.code,'name':dataset.name,'license_name':dataset.license_name},'stats':{**stats,'VERIFIED':verified,'ANNOTATIONS':ann_count,'TOTAL':sum(stats.values())},'classes':list(CLASSES),'frames':[serialize_frame(db,f) for f in rows]}

def freeze_dataset(db: Session, dataset: MLDataset, version: str, classes: list[str], notes=None):
    classes=[x.upper() for x in classes if x.upper() in CLASSES]
    if not classes: raise ValueError('Debe seleccionar al menos una clase')
    if db.scalar(select(MLDatasetVersion).where(MLDatasetVersion.dataset_id==dataset.id,MLDatasetVersion.version==version)): raise ValueError('Versión ya existe')
    frames=list(db.scalars(select(MLDatasetFrame).where(MLDatasetFrame.dataset_id==dataset.id,MLDatasetFrame.curation_status=='ACCEPTED',MLDatasetFrame.ground_truth_status=='VERIFIED').order_by(MLDatasetFrame.sha256)))
    if len(frames)<3: raise ValueError('Se requieren al menos 3 frames ACCEPTED + VERIFIED')
    root=dataset_root(dataset)/version/'COCO'; (root/'annotations').mkdir(parents=True,exist_ok=True)
    cats=[{'id':i+1,'name':c} for i,c in enumerate(classes)]; cmap={c:i+1 for i,c in enumerate(classes)}
    buckets={'train2017':[],'val2017':[],'test2017':[]}
    for i,f in enumerate(frames):
        bucket='test2017' if i%10==0 else ('val2017' if i%10==1 else 'train2017')
        buckets[bucket].append(f)
    total_ann=0
    for bucket,items in buckets.items():
        (root/bucket).mkdir(exist_ok=True); images=[]; annotations=[]; aid=1
        for iid,f in enumerate(items,1):
            src=frame_path(f); name=f'{f.id}.jpg'; shutil.copy2(src,root/bucket/name)
            images.append({'id':iid,'file_name':name,'width':f.width,'height':f.height})
            anns=list(db.scalars(select(MLGroundTruthAnnotation).where(MLGroundTruthAnnotation.frame_id==f.id,MLGroundTruthAnnotation.verified.is_(True))))
            for a in anns:
                if a.class_code not in cmap: continue
                x=a.x*f.width;y=a.y*f.height;w=a.width*f.width;h=a.height*f.height
                annotations.append({'id':aid,'image_id':iid,'category_id':cmap[a.class_code],'bbox':[x,y,w,h],'area':w*h,'iscrowd':0});aid+=1
        total_ann+=len(annotations)
        (root/'annotations'/f'instances_{bucket.replace("2017","")}2017.json').write_text(json.dumps({'images':images,'annotations':annotations,'categories':cats},ensure_ascii=False),encoding='utf-8')
    manifest={'dataset':dataset.code,'version':version,'classes':classes,'image_count':len(frames),'annotation_count':total_ann,'train_count':len(buckets['train2017']),'val_count':len(buckets['val2017']),'test_count':len(buckets['test2017']),'license_name':dataset.license_name,'created_at':utcnow().isoformat()}
    raw=json.dumps(manifest,sort_keys=True,ensure_ascii=False).encode(); digest=hashlib.sha256(raw).hexdigest();manifest['manifest_sha256']=digest
    (root/'DATASET_MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    v=MLDatasetVersion(dataset_id=dataset.id,version=version,status='FROZEN',classes=classes,image_count=len(frames),annotation_count=total_ann,train_count=len(buckets['train2017']),val_count=len(buckets['val2017']),test_count=len(buckets['test2017']),manifest_sha256=digest,storage_path=f'{dataset.code}/{version}/COCO',notes=notes,frozen_at=utcnow(),created_at=utcnow())
    db.add(v);db.flush();return v,manifest

def iou_xywh(a,b):
    ax,ay,aw,ah=a;bx,by,bw,bh=b
    x1=max(ax,bx);y1=max(ay,by);x2=min(ax+aw,bx+bw);y2=min(ay+ah,by+bh)
    inter=max(0,x2-x1)*max(0,y2-y1); union=aw*ah+bw*bh-inter
    return inter/union if union>0 else 0.0

def score_detections(gt, pred, iou_threshold=.5):
    classes=sorted(set([g['class_code'] for g in gt]+[p['class_code'] for p in pred])); by={}; T=F=N=0
    for c in classes:
        gs=[g for g in gt if g['class_code']==c]; ps=[p for p in pred if p['class_code']==c]; used=set();tp=0
        for p in sorted(ps,key=lambda x:x.get('confidence',0),reverse=True):
            best=(-1,0)
            for i,g in enumerate(gs):
                if i in used: continue
                v=iou_xywh(g['bbox'],p['bbox'])
                if v>best[1]:best=(i,v)
            if best[0]>=0 and best[1]>=iou_threshold: used.add(best[0]);tp+=1
        fp=len(ps)-tp;fn=len(gs)-tp;T+=tp;F+=fp;N+=fn
        by[c]={'tp':tp,'fp':fp,'fn':fn,'precision':round(tp/max(tp+fp,1),4),'recall':round(tp/max(tp+fn,1),4)}
    return {'tp':T,'fp':F,'fn':N,'precision':round(T/max(T+F,1),4),'recall':round(T/max(T+N,1),4),'f1':round(2*T/max(2*T+F+N,1),4),'by_class':by}

def evaluate_model(db: Session, dataset: MLDataset, model: VisionModelVersion, actor_id=None, camera_id=None, iou_threshold=.5, confidence_threshold=.35):
    run=MLEvaluationRun(organization_id=dataset.organization_id,dataset_id=dataset.id,model_version_id=model.id,camera_id=camera_id,status='RUNNING',iou_threshold=iou_threshold,confidence_threshold=confidence_threshold,created_by_user_id=actor_id,started_at=utcnow(),created_at=utcnow())
    db.add(run);db.flush()
    frames=list(db.scalars(select(MLDatasetFrame).where(MLDatasetFrame.dataset_id==dataset.id,MLDatasetFrame.curation_status=='ACCEPTED',MLDatasetFrame.ground_truth_status=='VERIFIED').limit(300)))
    detector=create_ppe_detector(model.backend,model.model_metadata or {},model.artifact_uri)
    gt_all=[]; pred_all=[]
    try:
        for f in frames:
            img=cv2.imread(str(frame_path(f)))
            if img is None: continue
            anns=list(db.scalars(select(MLGroundTruthAnnotation).where(MLGroundTruthAnnotation.frame_id==f.id,MLGroundTruthAnnotation.verified.is_(True))))
            for a in anns:
                if a.class_code in ('HELMET','VEST','SAFETY_SHOES'): gt_all.append({'class_code':a.class_code,'bbox':[a.x,a.y,a.width,a.height],'frame':str(f.id)})
            if hasattr(detector,'_detect_crop'):
                ds=detector._detect_crop(img,threshold=confidence_threshold)
                for d in ds:
                    x,y,w,h=d['bbox']; pred_all.append({'class_code':d['code'],'bbox':[x/f.width,y/f.height,w/f.width,h/f.height],'confidence':d['confidence'],'frame':str(f.id)})
        # Match only within same frame by scoring per frame and accumulating counts.
        agg={'tp':0,'fp':0,'fn':0,'by_class':{}}
        for f in frames:
            fid=str(f.id); s=score_detections([x for x in gt_all if x['frame']==fid],[x for x in pred_all if x['frame']==fid],iou_threshold)
            agg['tp']+=s['tp'];agg['fp']+=s['fp'];agg['fn']+=s['fn']
            for c,m in s['by_class'].items():
                b=agg['by_class'].setdefault(c,{'tp':0,'fp':0,'fn':0}); b['tp']+=m['tp'];b['fp']+=m['fp'];b['fn']+=m['fn']
        for c,b in agg['by_class'].items(): b['precision']=round(b['tp']/max(b['tp']+b['fp'],1),4);b['recall']=round(b['tp']/max(b['tp']+b['fn'],1),4)
        T,F,N=agg['tp'],agg['fp'],agg['fn'];agg.update({'precision':round(T/max(T+F,1),4),'recall':round(T/max(T+N,1),4),'f1':round(2*T/max(2*T+F+N,1),4),'samples':len(frames)})
        run.status='COMPLETED';run.sample_count=len(frames);run.metrics=agg;run.completed_at=utcnow();db.flush();return run
    except Exception as exc:
        run.status='FAILED';run.error_message=str(exc);run.completed_at=utcnow();db.flush();raise
