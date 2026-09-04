import json, uuid
from pathlib import Path
import cv2
import numpy as np
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.access import Permission, Role
from app.models.ml import MLDataset, MLDatasetVersion, MLModelDeployment, MLShadowObservation
from app.models.vision import VisionModelVersion
from app.services.ml_registry import create_deployment, shadow_summary
from app.services.ppe_runtime import IntelWorkerSafetyPPEDetector, _standard_detection_rows, _geti_boxes_labels, _yolox_demo_postprocess
from app.dataset_tool import build_coco


def make_camera(client,h,code='ML'):
    org=client.post('/api/v1/organizations',headers=h,json={'code':code+'ORG','name':'ML Org'}).json()
    site=client.post('/api/v1/sites',headers=h,json={'organization_id':org['id'],'code':'S','name':'Site'}).json()
    plant=client.post('/api/v1/plants',headers=h,json={'site_id':site['id'],'code':'P','name':'Plant'}).json()
    sec=client.post('/api/v1/sectors',headers=h,json={'plant_id':plant['id'],'code':'SEC','name':'Sector'}).json()
    cam=client.post('/api/v1/cameras',headers=h,json={'sector_id':sec['id'],'code':code+'CAM','name':'ML Camera','source_type':'DEMO_FILE','capture_fps':5}).json()
    return org,cam


def test_ml_permissions_seeded_and_consulta_is_read_only():
    with SessionLocal() as db:
        for code in ('ml.read','ml.manage','ml.train'): assert db.scalar(select(Permission).where(Permission.code==code))
        consulta=db.scalar(select(Role).where(Role.code=='CONSULTA')); codes={p.code for p in consulta.permissions}
        assert 'ml.read' in codes and 'ml.manage' not in codes and 'ml.train' not in codes


def test_bootstrap_seed_is_mit_and_not_production_certified():
    with SessionLocal() as db:
        m=db.scalar(select(VisionModelVersion).where(VisionModelVersion.code=='INTEL_WORKER_SAFETY_BOOTSTRAP'))
        assert m and m.license_name=='MIT' and m.backend=='openvino_ir_ppe'
        assert m.class_map=={'1':'HELMET','2':'VEST'}
        assert m.model_metadata['production_certified_for_hys'] is False


def test_detection_output_normalizer_and_intel_label_map():
    a=np.array([[[[0,1,.91,.1,.1,.3,.3],[0,2,.88,.2,.2,.6,.7]]]],dtype=np.float32)
    rows=_standard_detection_rows(a); assert rows.shape==(2,7)
    d=IntelWorkerSafetyPPEDetector.__new__(IntelWorkerSafetyPPEDetector)
    d.input_size=(600,600); d.input_layout='NCHW'; d.threshold=.35; d.class_thresholds={'HELMET':.57,'VEST':.525}; d.label_map={1:'HELMET',2:'VEST'}
    class Port: pass
    port=Port(); d.input_port=Port(); d.output_ports=[port]
    class Compiled:
        def __call__(self, inputs):
            return {port:a}
    d.compiled_model=Compiled(); out=d._detect_crop(np.zeros((100,200,3),np.uint8))
    assert [x['code'] for x in out]==['HELMET','VEST']



def test_geti_boxes_labels_normalizer():
    boxes=np.array([[[10,20,110,220,.91],[30,40,130,240,.88]]],dtype=np.float32)
    labels=np.array([[1,0]],dtype=np.int64)
    rows=_geti_boxes_labels([('boxes',boxes),('labels',labels)])
    assert len(rows)==2
    assert rows[0][0]==1 and abs(rows[0][1]-.91)<1e-5
    assert rows[1][0]==0 and abs(rows[1][1]-.88)<1e-5


def test_geti_two_output_detector_mapping_and_scaling():
    d=IntelWorkerSafetyPPEDetector.__new__(IntelWorkerSafetyPPEDetector)
    d.input_size=(640,640); d.input_layout='NCHW'; d.threshold=.35
    d.class_thresholds={'HELMET':.57,'VEST':.525}; d.label_map={1:'HELMET',2:'VEST'}
    d.geti_label_map={0:'VEST',1:'HELMET'}
    class Port:
        def __init__(self,name): self.name=name
        def get_any_name(self): return self.name
    bp,lp=Port('boxes'),Port('labels'); d.input_port=Port('images'); d.output_ports=[bp,lp]
    boxes=np.array([[[64,64,192,192,.91],[128,128,384,448,.88]]],dtype=np.float32)
    labels=np.array([[1,0]],dtype=np.int64)
    class Compiled:
        def __call__(self,inputs): return {bp:boxes,lp:labels}
    d.compiled_model=Compiled()
    out=d._detect_crop(np.zeros((320,320,3),np.uint8))
    assert [x['code'] for x in out]==['HELMET','VEST']
    # 640 model pixels -> 320 crop pixels
    assert out[0]['bbox'][0]==32 and out[0]['bbox'][2]==64


def test_compiled_graph_shape_precedence_is_documented():
    # Regression guard for v1.0.1: the registry said 600x600 while the pinned
    # OpenVINO graph is 640x640. Runtime must derive dimensions from the graph.
    src=Path(__import__('app.services.ppe_runtime',fromlist=['x']).__file__).read_text(encoding='utf-8')
    assert "derived or meta.get('input_size')" in src

def test_yolox_grid_decode_shape():
    size=(416,416); n=sum((size[0]//s)*(size[1]//s) for s in (8,16,32))
    x=np.zeros((1,n,8),dtype=np.float32); out=_yolox_demo_postprocess(x,size)
    assert out.shape==x.shape and np.isfinite(out).all()


def test_dataset_and_training_run_api_uses_apache_stack(client,admin_headers):
    org,_=make_camera(client,admin_headers,'DS')
    r=client.post('/api/v1/ml/datasets',headers=admin_headers,json={'organization_id':org['id'],'code':'HYS-PPE','name':'HYS PPE','license_name':'PROPRIETARY-HYS'}); assert r.status_code==200
    did=r.json()['id']
    r=client.post(f'/api/v1/ml/datasets/{did}/versions',headers=admin_headers,json={'version':'v0001','classes':['HELMET','VEST','SAFETY_SHOES'],'image_count':10,'annotation_count':20,'train_count':8,'val_count':1,'test_count':1,'manifest_sha256':'a'*64,'storage_path':'HYS-PPE/v0001/COCO','freeze':True}); assert r.status_code==200
    vid=r.json()['id']
    r=client.post('/api/v1/ml/training-runs',headers=admin_headers,json={'dataset_version_id':vid,'base_model':'yolox_nano','epochs':5,'image_size':416,'batch_size':2,'device':'cuda'}); assert r.status_code==200
    cmd=r.json()['command_line']; assert 'trainer' in cmd and 'yolox' in cmd.lower() and 'ultralytics' not in cmd.lower()


def test_model_register_and_shadow_deployment(client,admin_headers,tmp_path,monkeypatch):
    org,cam=make_camera(client,admin_headers,'REG')
    monkeypatch.setattr(settings,'hys_model_root',str(tmp_path))
    art=tmp_path/'hys.onnx'; art.write_bytes(b'fake-onnx-for-registry-test')
    import hashlib; sha=hashlib.sha256(art.read_bytes()).hexdigest()
    r=client.post('/api/v1/ml/models/register',headers=admin_headers,json={'organization_id':org['id'],'code':'HYS_PPE_TEST','name':'HYS PPE Test','version':'1.0','artifact_uri':'hys.onnx','artifact_sha256':sha,'class_map':{'0':'HELMET','1':'VEST','2':'SAFETY_SHOES'},'input_width':416,'input_height':416,'metrics':{'map50':.71}}); assert r.status_code==200 and r.json()['available'] is True
    mid=r.json()['id']
    r=client.post('/api/v1/ml/deployments',headers=admin_headers,json={'model_version_id':mid,'camera_id':cam['id'],'mode':'SHADOW'}); assert r.status_code==200 and r.json()['mode']=='SHADOW'


def test_bootstrap_cannot_be_promoted_directly_to_production(client,admin_headers,tmp_path,monkeypatch):
    org,cam=make_camera(client,admin_headers,'SAFE')
    monkeypatch.setattr(settings,'hys_model_root',str(tmp_path)); p=tmp_path/'bootstrap/intel-worker-safety'; p.mkdir(parents=True); (p/'model.xml').write_bytes(b'x'); (p/'model.bin').write_bytes(b'y')
    with SessionLocal() as db:
        m=db.scalar(select(VisionModelVersion).where(VisionModelVersion.code=='INTEL_WORKER_SAFETY_BOOTSTRAP')); m.artifact_uri='bootstrap/intel-worker-safety/model.xml'; m.artifact_sha256=None; m.active=True; db.commit(); mid=m.id
    r=client.post('/api/v1/ml/deployments',headers=admin_headers,json={'model_version_id':str(mid),'camera_id':cam['id'],'mode':'PRODUCTION'})
    assert r.status_code==400 and 'no certificado' in r.text.lower()


def test_shadow_summary_counts_agreement(client,admin_headers,tmp_path,monkeypatch):
    org,cam=make_camera(client,admin_headers,'SH')
    with SessionLocal() as db:
        oid=uuid.UUID(org['id']); cid=uuid.UUID(cam['id']); base=db.scalar(select(VisionModelVersion).where(VisionModelVersion.code=='PPE_REGION_SVM_BASELINE'))
        dep=MLModelDeployment(organization_id=oid,camera_id=cid,model_version_id=base.id,mode='SHADOW',enabled=True); db.add(dep); db.flush()
        db.add_all([MLShadowObservation(organization_id=oid,camera_id=cid,deployment_id=dep.id,track_id='T1',ppe_code='HELMET',baseline_status='OK',candidate_status='OK',agreement=True),MLShadowObservation(organization_id=oid,camera_id=cid,deployment_id=dep.id,track_id='T1',ppe_code='VEST',baseline_status='OK',candidate_status='NO_DETECTADO',agreement=False)]); db.commit()
        s=shadow_summary(db,oid,camera_id=cid); assert s['samples']==2 and s['agreements']==1 and s['agreement_ratio']==.5


def test_dataset_tool_builds_coco_from_yolo(tmp_path):
    src=tmp_path/'source'; (src/'images').mkdir(parents=True); (src/'labels').mkdir()
    for i in range(10):
        p=src/'images'/f'{i}.jpg'; cv2.imwrite(str(p),np.full((100,120,3),80+i,np.uint8)); (src/'labels'/f'{i}.txt').write_text('0 0.5 0.2 0.3 0.2\n1 0.5 0.55 0.5 0.4\n',encoding='utf-8')
    out=tmp_path/'COCO'
    class A: pass
    a=A(); a.source=str(src); a.output=str(out); a.classes='HELMET,VEST,SAFETY_SHOES'; a.version='v0001'; a.license='PROPRIETARY-HYS'; a.val=.1; a.test=.1; a.seed=42; a.allow_empty=False
    build_coco(a)
    man=json.loads((out/'DATASET_MANIFEST.json').read_text()); assert man['image_count']==10 and man['annotation_count']==20 and man['train_count']==8 and man['val_count']==1 and man['test_count']==1
    assert (out/'annotations/instances_train2017.json').exists()


def test_ml_overview_declares_no_ultralytics(client,admin_headers):
    org,_=make_camera(client,admin_headers,'OV')
    r=client.get(f'/api/v1/ml/overview?organization_id={org["id"]}',headers=admin_headers); assert r.status_code==200
    p=r.json()['policy']; assert p['ultralytics_used'] is False and 'YOLOX' in p['training_stack'] and 'ONNX' in p['runtime']
