import argparse, json, uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.camera import Camera
from app.models.organization import Organization
from app.models.ml import MLDataset, MLDatasetVersion, MLModelDeployment
from app.models.vision import VisionModelVersion
from app.services.ml_registry import create_deployment, file_sha256, model_available, serialize_model, shadow_summary


def _model(db, code):
    m=db.scalar(select(VisionModelVersion).where(VisionModelVersion.code==code))
    if not m: raise SystemExit(f'Modelo inexistente: {code}')
    return m

def _org(db, code):
    o=db.scalar(select(Organization).where(Organization.code==code))
    if not o: raise SystemExit(f'Organización inexistente: {code}')
    return o

def _camera(db, org, code):
    if not code: return None
    c=db.scalar(select(Camera).where(Camera.organization_id==org.id,Camera.code==code))
    if not c: raise SystemExit(f'Cámara inexistente: {code}')
    return c


def activate_intel(args):
    rel=args.artifact_uri; p=Path(rel)
    if not p.is_absolute(): p=Path(settings.hys_model_root)/p
    if not p.exists(): raise SystemExit(f'Artifact XML inexistente: {p}')
    b=p.with_suffix('.bin')
    if not b.exists(): raise SystemExit(f'Artifact BIN inexistente: {b}')
    with SessionLocal() as db:
        m=_model(db,'INTEL_WORKER_SAFETY_BOOTSTRAP')
        meta=dict(m.model_metadata or {})
        meta.update({'classes':['HELMET','VEST'],'input_size':[600,600],'default_threshold':0.35,'helmet_threshold':0.57,'vest_threshold':0.525,'detection_output_label_map':{'1':'HELMET','2':'VEST'},'artifact_bin_sha256':file_sha256(b),'production_certified_for_hys':False})
        m.artifact_uri=rel; m.artifact_sha256=file_sha256(p); m.active=True; m.model_stage='REGISTERED'; m.framework='OpenVINO IR via OpenCV DNN'; m.model_metadata=meta; m.class_map={'1':'HELMET','2':'VEST'}
        db.commit(); db.refresh(m); print('BLOCK9_INTEL_ACTIVATED '+json.dumps(serialize_model(m),default=str,separators=(',',':')))


def deploy(args):
    with SessionLocal() as db:
        m=_model(db,args.model)
        if not model_available(m): raise SystemExit('Artifact no disponible o SHA inválido')
        org=_org(db,args.organization); cam=_camera(db,org,args.camera)
        dep=create_deployment(db,org.id,m,cam.id if cam else None,args.mode,None)
        if args.mode=='PRODUCTION': m.model_stage='PRODUCTION'; m.approved_at=datetime.now(timezone.utc)
        elif m.model_stage=='REGISTERED': m.model_stage='SHADOW'
        db.commit(); print(f'BLOCK9_DEPLOYMENT_OK id={dep.id} model={m.code} mode={dep.mode} camera={args.camera or "ORG"}')


def register_dataset(args):
    mp=Path(args.manifest); data=json.loads(mp.read_text(encoding='utf-8'))
    with SessionLocal() as db:
        org=_org(db,args.organization)
        d=db.scalar(select(MLDataset).where(MLDataset.organization_id==org.id,MLDataset.code==args.code))
        if not d:
            d=MLDataset(organization_id=org.id,code=args.code,name=args.name,description='Dataset HYS propio para EPP.',license_name=data.get('license','PROPRIETARY-HYS'),source_url=None,active=True)
            db.add(d); db.flush()
        v=db.scalar(select(MLDatasetVersion).where(MLDatasetVersion.dataset_id==d.id,MLDatasetVersion.version==data['version']))
        if not v:
            v=MLDatasetVersion(dataset_id=d.id,version=data['version'],status='FROZEN',classes=data['classes'],image_count=data['image_count'],annotation_count=data['annotation_count'],train_count=data['train_count'],val_count=data['val_count'],test_count=data['test_count'],manifest_sha256=data['manifest_sha256'],storage_path=args.storage_path,notes='Generado por HYS Dataset Tool',frozen_at=datetime.now(timezone.utc))
            db.add(v)
        db.commit(); db.refresh(v)
        print(f'BLOCK9_DATASET_REGISTERED dataset={d.code} version={v.version} version_id={v.id} images={v.image_count} anns={v.annotation_count}')


def register_onnx(args):
    mp=Path(args.manifest); man=json.loads(mp.read_text(encoding='utf-8'))
    rel=args.artifact_uri; p=Path(rel)
    if not p.is_absolute(): p=Path(settings.hys_model_root)/p
    if not p.exists(): raise SystemExit(f'ONNX inexistente: {p}')
    with SessionLocal() as db:
        org=_org(db,args.organization)
        code=args.code or ('HYS_PPE_'+man['run_id'].replace('-','_').upper())
        m=db.scalar(select(VisionModelVersion).where(VisionModelVersion.code==code))
        if m: raise SystemExit(f'Modelo ya registrado: {code}')
        class_map={str(i):c for i,c in enumerate(man['classes'])}
        m=VisionModelVersion(code=code,name=args.name or code,provider='HYS Vision IA',backend='onnx_yolox_ppe',detector_type='PPE',version=args.version,license_name='HYS-PROPRIETARY',commercial_use=True,active=True,is_default=False,notes='Modelo HYS entrenado con YOLOX Apache-2.0; requiere SHADOW antes de producción.',model_metadata={'classes':man['classes'],'class_map':class_map,'input_width':man['image_size'],'input_height':man['image_size'],'decode_grid':False,'production_certified_for_hys':False,'training_stack':'YOLOX 0.3.0 Apache-2.0'},artifact_uri=rel,artifact_sha256=file_sha256(p),framework='YOLOX 0.3.0 -> ONNX Runtime',model_stage='REGISTERED',input_width=man['image_size'],input_height=man['image_size'],class_map=class_map,metrics_json=man.get('metrics') or {})
        db.add(m); db.commit(); db.refresh(m)
        print('BLOCK9_ONNX_REGISTERED '+json.dumps(serialize_model(m),default=str,separators=(',',':')))


def promote(args):
    with SessionLocal() as db:
        org=_org(db,args.organization); cam=_camera(db,org,args.camera); m=_model(db,args.model)
        dep=db.scalar(select(MLModelDeployment).where(MLModelDeployment.organization_id==org.id,MLModelDeployment.camera_id==cam.id,MLModelDeployment.model_version_id==m.id,MLModelDeployment.mode=='SHADOW',MLModelDeployment.enabled.is_(True)).order_by(MLModelDeployment.started_at.desc()))
        if not dep: raise SystemExit('No existe deployment SHADOW activo del modelo en la cámara')
        sm=shadow_summary(db,org.id,camera_id=cam.id,deployment_id=dep.id)
        if sm['samples']<args.min_samples or sm['agreement_ratio']<args.min_agreement:
            raise SystemExit(f'SHADOW insuficiente: samples={sm["samples"]}/{args.min_samples} agreement={sm["agreement_ratio"]:.3f}/{args.min_agreement:.3f}')
        meta=dict(m.model_metadata or {}); meta['production_certified_for_hys']=True; meta['promotion_shadow_summary']=sm; m.model_metadata=meta; m.model_stage='APPROVED'; db.commit()
        prod=create_deployment(db,org.id,m,cam.id,'PRODUCTION',None); m.model_stage='PRODUCTION'; m.approved_at=datetime.now(timezone.utc); db.commit()
        print(f'BLOCK9_PROMOTE_OK deployment={prod.id} samples={sm["samples"]} agreement={sm["agreement_ratio"]:.4f}')


def list_models(args):
    with SessionLocal() as db:
        for m in db.scalars(select(VisionModelVersion).where(VisionModelVersion.detector_type=='PPE').order_by(VisionModelVersion.created_at)):
            print(f'{m.code}\t{m.backend}\t{m.model_stage}\tactive={m.active}\tavailable={model_available(m)}\tartifact={m.artifact_uri}')


def main():
    ap=argparse.ArgumentParser('HYS ML CLI'); sp=ap.add_subparsers(dest='cmd',required=True)
    a=sp.add_parser('activate-intel'); a.add_argument('--artifact-uri',default='bootstrap/intel-worker-safety/model.xml'); a.set_defaults(fn=activate_intel)
    d=sp.add_parser('deploy'); d.add_argument('--model',required=True); d.add_argument('--mode',choices=['SHADOW','PRODUCTION'],required=True); d.add_argument('--organization',default='DEMO-HYS'); d.add_argument('--camera'); d.set_defaults(fn=deploy)
    rd=sp.add_parser('register-dataset'); rd.add_argument('--manifest',required=True); rd.add_argument('--storage-path',required=True); rd.add_argument('--organization',default='DEMO-HYS'); rd.add_argument('--code',default='HYS-PPE'); rd.add_argument('--name',default='HYS PPE Dataset'); rd.set_defaults(fn=register_dataset)
    ro=sp.add_parser('register-onnx'); ro.add_argument('--manifest',required=True); ro.add_argument('--artifact-uri',required=True); ro.add_argument('--organization',default='DEMO-HYS'); ro.add_argument('--code'); ro.add_argument('--name'); ro.add_argument('--version',default='1.0.0'); ro.set_defaults(fn=register_onnx)
    pr=sp.add_parser('promote'); pr.add_argument('--model',required=True); pr.add_argument('--organization',default='DEMO-HYS'); pr.add_argument('--camera',required=True); pr.add_argument('--min-samples',type=int,default=300); pr.add_argument('--min-agreement',type=float,default=.85); pr.set_defaults(fn=promote)
    l=sp.add_parser('list-models'); l.set_defaults(fn=list_models)
    args=ap.parse_args(); args.fn(args)
if __name__=='__main__': main()
