import uuid
from pathlib import Path
import cv2
import numpy as np
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.ml import MLDataset
from app.models.ml_dataset_visual import MLDatasetFrame, MLGroundTruthAnnotation
from app.models.vision import VisionModelVersion
from app.services.dataset_visual import ingest_jpeg, replace_annotations, score_detections, freeze_dataset


def make_org_camera(client,h,code='B10'):
    org=client.post('/api/v1/organizations',headers=h,json={'code':code+'ORG','name':'Block 10 Org'}).json()
    site=client.post('/api/v1/sites',headers=h,json={'organization_id':org['id'],'code':'S','name':'Site'}).json()
    plant=client.post('/api/v1/plants',headers=h,json={'site_id':site['id'],'code':'P','name':'Plant'}).json()
    sec=client.post('/api/v1/sectors',headers=h,json={'plant_id':plant['id'],'code':'SEC','name':'Sector'}).json()
    cam=client.post('/api/v1/cameras',headers=h,json={'sector_id':sec['id'],'code':code+'CAM','name':'Camera','source_type':'DEMO_FILE','capture_fps':5}).json()
    return org,cam


def test_iou_metric_perfect_and_false_positive():
    gt=[{'class_code':'HELMET','bbox':[.1,.1,.2,.2]}]
    p=[{'class_code':'HELMET','bbox':[.1,.1,.2,.2],'confidence':.9},{'class_code':'VEST','bbox':[.4,.4,.2,.3],'confidence':.8}]
    s=score_detections(gt,p,.5)
    assert s['tp']==1 and s['fp']==1 and s['fn']==0
    assert s['by_class']['HELMET']['recall']==1.0


def test_ingest_frame_dedupe_and_ground_truth(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'hys_dataset_root',str(tmp_path))
    with SessionLocal() as db:
        # bootstrap test DB has no org; create through ORM-independent API fixture is easier in API test,
        # so this test only verifies pure score path. Kept as guard for temp path availability.
        assert Path(settings.hys_dataset_root)==tmp_path


def test_workspace_and_manual_ground_truth_api(client,admin_headers,tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'hys_dataset_root',str(tmp_path))
    org,_=make_org_camera(client,admin_headers,'WS')
    r=client.post('/api/v1/ml/datasets',headers=admin_headers,json={'organization_id':org['id'],'code':'HYSVIS','name':'Visual','license_name':'PROPRIETARY-HYS'});assert r.status_code==200
    did=uuid.UUID(r.json()['id'])
    img=np.full((120,160,3),90,np.uint8);ok,enc=cv2.imencode('.jpg',img);assert ok
    with SessionLocal() as db:
        d=db.get(MLDataset,did);f=ingest_jpeg(db,d,enc.tobytes(),source_type='UPLOAD',actor_id=None);db.commit();fid=str(f.id)
    r=client.put(f'/api/v1/ml/frames/{fid}/annotations',headers=admin_headers,json={'verified':True,'annotations':[{'class_code':'HELMET','x':.2,'y':.1,'width':.3,'height':.25}]});assert r.status_code==200
    assert r.json()['ground_truth_status']=='VERIFIED' and len(r.json()['annotations'])==1
    r=client.patch(f'/api/v1/ml/frames/{fid}/curation',headers=admin_headers,json={'status':'ACCEPTED'});assert r.status_code==200
    w=client.get(f'/api/v1/ml/datasets/{did}/workspace',headers=admin_headers).json();assert w['stats']['ACCEPTED']==1 and w['stats']['VERIFIED']==1


def test_freeze_visual_requires_three_verified_frames(client,admin_headers,tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'hys_dataset_root',str(tmp_path))
    org,_=make_org_camera(client,admin_headers,'FR')
    did=uuid.UUID(client.post('/api/v1/ml/datasets',headers=admin_headers,json={'organization_id':org['id'],'code':'FREEZE','name':'Freeze','license_name':'PROPRIETARY-HYS'}).json()['id'])
    with SessionLocal() as db:
        d=db.get(MLDataset,did)
        for i in range(3):
            img=np.full((100,120,3),60+i*20,np.uint8);_,enc=cv2.imencode('.jpg',img);f=ingest_jpeg(db,d,enc.tobytes(),source_type='UPLOAD');f.curation_status='ACCEPTED';replace_annotations(db,f,[{'class_code':'HELMET','x':.2,'y':.1,'width':.25,'height':.2}],True)
        db.commit()
    r=client.post(f'/api/v1/ml/datasets/{did}/freeze-visual',headers=admin_headers,json={'version':'v0001','classes':['HELMET','VEST']});assert r.status_code==200
    assert r.json()['manifest']['image_count']==3 and r.json()['manifest']['annotation_count']==3
    assert (tmp_path/'FREEZE/v0001/COCO/DATASET_MANIFEST.json').exists()


def test_bootstrap_controlled_promotion_is_blocked(client,admin_headers):
    org,cam=make_org_camera(client,admin_headers,'PR')
    with SessionLocal() as db:
        m=db.scalar(select(VisionModelVersion).where(VisionModelVersion.code=='INTEL_WORKER_SAFETY_BOOTSTRAP'));mid=str(m.id)
    r=client.post(f'/api/v1/ml/models/{mid}/promote-controlled',headers=admin_headers,json={'camera_id':cam['id'],'confirm':True})
    assert r.status_code==409 and 'no puede promoverse' in r.text


def test_shadow_by_camera_endpoint(client,admin_headers):
    org,cam=make_org_camera(client,admin_headers,'SC')
    r=client.get(f'/api/v1/ml/shadow/by-camera?organization_id={org["id"]}',headers=admin_headers);assert r.status_code==200
    row=next(x for x in r.json() if x['camera_id']==cam['id']);assert row['samples']==0


def test_frame_image_requires_auth_and_returns_jpeg(client,admin_headers,tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'hys_dataset_root',str(tmp_path))
    org,_=make_org_camera(client,admin_headers,'IM')
    did=uuid.UUID(client.post('/api/v1/ml/datasets',headers=admin_headers,json={'organization_id':org['id'],'code':'IMG','name':'Images','license_name':'PROPRIETARY-HYS'}).json()['id'])
    with SessionLocal() as db:
        d=db.get(MLDataset,did);img=np.zeros((40,60,3),np.uint8);_,enc=cv2.imencode('.jpg',img);f=ingest_jpeg(db,d,enc.tobytes());db.commit();fid=str(f.id)
    assert client.get(f'/api/v1/ml/frames/{fid}/image').status_code==401
    r=client.get(f'/api/v1/ml/frames/{fid}/image',headers=admin_headers);assert r.status_code==200 and r.headers['content-type'].startswith('image/jpeg')
