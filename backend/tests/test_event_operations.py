import io
import uuid

import cv2
import numpy as np
from datetime import datetime, timezone
from unittest.mock import patch
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.access import User
from app.models.camera import Camera
from app.models.safety import PPEType, SafetyDetectionEvent, SafetyEventAction, SafetyEventEvidence, SafetyEventNote, Zone
from app.services.event_evidence import capture_event_evidence, sha256_bytes
from app.services.safety_events import open_or_get_event


def create_event(client,headers,code='B6'):
    o=client.post('/api/v1/organizations',headers=headers,json={'code':code+'ORG','name':'Block6 Org'}).json(); si=client.post('/api/v1/sites',headers=headers,json={'organization_id':o['id'],'code':'S','name':'Site'}).json(); pl=client.post('/api/v1/plants',headers=headers,json={'site_id':si['id'],'code':'P','name':'Plant'}).json(); sec=client.post('/api/v1/sectors',headers=headers,json={'plant_id':pl['id'],'code':'SEC','name':'Sector'}).json(); cam=client.post('/api/v1/cameras',headers=headers,json={'sector_id':sec['id'],'code':code+'CAM','name':'Cam','source_type':'DEMO_FILE','capture_fps':5}).json(); zone=client.post('/api/v1/zones',headers=headers,json={'camera_id':cam['id'],'code':'Z','name':'Zone','polygon_points':[{'x':.1,'y':.1},{'x':.9,'y':.1},{'x':.9,'y':.9},{'x':.1,'y':.9}]}).json()
    with SessionLocal() as db:
        cam_obj=db.get(Camera,uuid.UUID(cam['id'])); ppe=db.scalar(select(PPEType).where(PPEType.code=='HELMET')); z=db.get(Zone,uuid.UUID(zone['id'])); now=datetime.now(timezone.utc); action={'type':'OPEN','key':f'{cam_obj.id}:TRACK-0001:HELMET','track_id':'TRACK-0001','rule':{'zone_id':str(z.id),'ppe_type_id':str(ppe.id),'ppe_code':'HELMET','ppe_name':ppe.name,'requirement':'REQUIRED','severity':'ALTA'},'observed_status':'NO_DETECTADO','confidence':.2,'missing_span_seconds':2,'consensus_ratio':1.0,'missing_observations':3,'evaluable_observations':3}; ev,_=open_or_get_event(db,cam_obj,action,{'engine_version':'0.7.0'},15,now); db.commit(); eid=str(ev.id)
    return o,cam,eid


def test_block6_defaults_and_detail(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'D1')
    r=client.get(f'/api/v1/safety-events/{eid}',headers=admin_headers); assert r.status_code==200; b=r.json(); assert b['operational_status']=='NEW' and b['review_outcome']=='PENDING' and b['evidence_status']=='PENDING' and b['evidence_count']==0


def test_acknowledge_and_response_time(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'A1'); r=client.post(f'/api/v1/safety-events/{eid}/acknowledge',headers=admin_headers); assert r.status_code==200; b=r.json(); assert b['operational_status']=='ACKNOWLEDGED' and b['acknowledged_at'] and b['response_seconds']>=0
    tl=client.get(f'/api/v1/safety-events/{eid}/timeline',headers=admin_headers).json(); assert any(x['action']=='ACKNOWLEDGE' for x in tl)


def test_notes_are_append_only_timeline(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'N1'); r=client.post(f'/api/v1/safety-events/{eid}/notes',headers=admin_headers,json={'body':'Verificación de campo solicitada'}); assert r.status_code==201
    tl=client.get(f'/api/v1/safety-events/{eid}/timeline',headers=admin_headers).json(); assert any(x['type']=='NOTE' and x['body']=='Verificación de campo solicitada' for x in tl)


def test_false_positive_resolves_operationally_not_technical_detection(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'F1'); r=client.post(f'/api/v1/safety-events/{eid}/review',headers=admin_headers,json={'outcome':'FALSE_POSITIVE','notes':'Reflejo de luminaria'}); assert r.status_code==200; b=r.json(); assert b['operational_status']=='RESOLVED' and b['review_outcome']=='FALSE_POSITIVE' and b['status']=='OPEN' and b['resolved_at']
    summary=client.get('/api/v1/safety-events/summary',headers=admin_headers).json(); assert summary['active']==0


def test_confirm_review_then_operational_resolve(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'R1'); b=client.post(f'/api/v1/safety-events/{eid}/review',headers=admin_headers,json={'outcome':'CONFIRMED','notes':'Incumplimiento visual confirmado'}).json(); assert b['operational_status']=='IN_REVIEW' and b['review_outcome']=='CONFIRMED'
    b=client.post(f'/api/v1/safety-events/{eid}/resolve',headers=admin_headers,json={'note':'Supervisor informado y condición corregida'}).json(); assert b['operational_status']=='RESOLVED' and b['resolution_seconds']>=0


def test_assign_user_same_org_and_reject_cross_org(client,admin_headers):
    org,_,eid=create_event(client,admin_headers,'AS1')
    r=client.post('/api/v1/users',headers=admin_headers,json={'organization_id':org['id'],'email':'resp@example.org','full_name':'Responsable HYS','password':'Password-12345!','role_codes':['RESPONSABLE_HYS']}); assert r.status_code==201; uid=r.json()['id']
    b=client.post(f'/api/v1/safety-events/{eid}/assign',headers=admin_headers,json={'user_id':uid}).json(); assert b['assigned_to_user_id']==uid and b['assigned_to_name']=='Responsable HYS'
    ass=client.get(f'/api/v1/safety-events/assignees?event_id={eid}',headers=admin_headers).json(); ids={x['id'] for x in ass}; assert uid in ids
    with SessionLocal() as db:
        global_admin=db.scalar(select(User).where(User.organization_id.is_(None))); assert global_admin is not None; global_uid=str(global_admin.id)
    assert global_uid in ids
    b=client.post(f'/api/v1/safety-events/{eid}/assign',headers=admin_headers,json={'user_id':global_uid}).json(); assert b['assigned_to_user_id']==global_uid and b['assigned_to_name']=='Administrador HYS Vision'
    other=client.post('/api/v1/organizations',headers=admin_headers,json={'code':'OTHER','name':'Other Org'}).json()
    ru=client.post('/api/v1/users',headers=admin_headers,json={'organization_id':other['id'],'email':'other@example.org','full_name':'Other User','password':'Password-12345!','role_codes':['RESPONSABLE_HYS']}); assert ru.status_code==201
    bad=client.post(f'/api/v1/safety-events/{eid}/assign',headers=admin_headers,json={'user_id':ru.json()['id']}); assert bad.status_code==400


def test_evidence_hash_and_application_immutability(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'E1')
    raw=b'jpeg-evidence-content'; overlay=b'annotated-evidence-content'
    class FakeMinio:
        store={}
        def stat_object(self,b,k):
            if k not in self.store: raise Exception('not found')
        def put_object(self,b,k,stream,length,content_type=None): self.store[k]=stream.read()
    fake=FakeMinio()
    with SessionLocal() as db, patch('app.services.event_evidence.minio_client',return_value=fake):
        ev=db.get(SafetyDetectionEvent,uuid.UUID(eid)); capture_event_evidence(db,ev,raw,overlay,[],datetime.now(timezone.utc).isoformat(),1.0); db.commit(); assert ev.evidence_count==2 and ev.evidence_status=='READY'
        rows=list(db.scalars(select(SafetyEventEvidence).where(SafetyEventEvidence.event_id==ev.id))); assert len(rows)==2 and all(x.immutable for x in rows); assert rows[0].sha256==sha256_bytes(raw) or rows[1].sha256==sha256_bytes(raw)
    out=client.get(f'/api/v1/safety-events/{eid}/evidence',headers=admin_headers); assert out.status_code==200 and len(out.json())==2 and all(x['immutable'] for x in out.json())


def test_evidence_preview_endpoint_returns_h264_and_preserves_source_sha(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'PV1')
    frames=[]
    for i in range(4):
        img=np.zeros((120,160,3),dtype=np.uint8); cv2.rectangle(img,(20+i*4,20),(80+i*4,100),(255,255,255),-1); ok,j=cv2.imencode('.jpg',img); assert ok; frames.append((str(i),j.tobytes()))
    from app.services.event_evidence import encode_clip
    clip=encode_clip(frames,1.0); assert clip
    class FakeResponse:
        def __init__(self,data): self.data=data
        def read(self): return self.data
        def close(self): pass
        def release_conn(self): pass
    class FakeMinio:
        store={}
        def stat_object(self,b,k):
            if k not in self.store: raise Exception('not found')
        def put_object(self,b,k,stream,length,content_type=None): self.store[k]=stream.read()
        def get_object(self,b,k): return FakeResponse(self.store[k])
    fake=FakeMinio()
    with SessionLocal() as db, patch('app.services.event_evidence.minio_client',return_value=fake):
        ev=db.get(SafetyDetectionEvent,uuid.UUID(eid)); capture_event_evidence(db,ev,frames[-1][1],frames[-1][1],frames,datetime.now(timezone.utc).isoformat(),1.0); db.commit(); row=db.scalar(select(SafetyEventEvidence).where(SafetyEventEvidence.event_id==ev.id,SafetyEventEvidence.kind=='CLIP_PRE_EVENT')); assert row; evid=str(row.id); source_sha=row.sha256
        with patch('app.services.event_evidence.minio_client',return_value=fake):
            r=client.get(f'/api/v1/safety-events/evidence/{evid}/preview',headers=admin_headers)
        assert r.status_code==200 and r.headers['content-type'].startswith('video/mp4') and r.headers['x-source-evidence-sha256']==source_sha and len(r.content)>500


def test_invalid_review_outcome_rejected(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'I1'); r=client.post(f'/api/v1/safety-events/{eid}/review',headers=admin_headers,json={'outcome':'AUTO_FIRE','notes':'x'}); assert r.status_code==422


def test_manage_permission_seeded_for_operational_roles():
    from app.models.access import Permission,Role
    with SessionLocal() as db:
        p=db.scalar(select(Permission).where(Permission.code=='safety_event.manage')); assert p is not None
        for code in ['SUPERADMIN','ADMIN_EMPRESA','RESPONSABLE_HYS','OPERADOR_MONITOREO']:
            role=db.scalar(select(Role).where(Role.code==code)); assert 'safety_event.manage' in {x.code for x in role.permissions}
        for code in ['AUDITOR','CONSULTA']:
            role=db.scalar(select(Role).where(Role.code==code)); assert 'safety_event.manage' not in {x.code for x in role.permissions}


def test_superadmin_remains_assignable_with_legacy_org_scope(client,admin_headers):
    org,_,eid=create_event(client,admin_headers,'ASLEG')
    other=client.post('/api/v1/organizations',headers=admin_headers,json={'code':'LEGOTHER','name':'Legacy Other Org'}).json()
    with SessionLocal() as db:
        admin=db.scalar(select(User).where(User.roles.any()))
        # Find the authenticated bootstrap SUPERADMIN deterministically.
        admins=list(db.scalars(select(User)))
        admin=next(u for u in admins if any(r.code=='SUPERADMIN' for r in u.roles))
        original_org=admin.organization_id
        admin.organization_id=uuid.UUID(other['id'])
        admin_id=str(admin.id)
        admin_email=admin.email
        db.commit()
    try:
        ass=client.get(f'/api/v1/safety-events/assignees?event_id={eid}',headers=admin_headers)
        assert ass.status_code==200
        rows=ass.json(); ids={x['id'] for x in rows}
        assert admin_id in ids
        b=client.post(f'/api/v1/safety-events/{eid}/assign',headers=admin_headers,json={'user_id':admin_id})
        assert b.status_code==200
        assert b.json()['assigned_to_user_id']==admin_id
    finally:
        with SessionLocal() as db:
            admin=db.get(User,uuid.UUID(admin_id)); admin.organization_id=original_org; db.commit()
