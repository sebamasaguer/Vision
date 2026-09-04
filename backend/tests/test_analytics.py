import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.access import Permission, Role
from app.models.camera import Camera
from app.models.organization import Organization
from app.models.safety import AlertPolicy, PPEType, SafetyDetectionEvent, Zone
from app.services.pilot_cleanup import cleanup_pilot
from app.services.safety_events import open_or_get_event

def make_event(client,h,code='A8',severity='ALTA'):
 org=client.post('/api/v1/organizations',headers=h,json={'code':code+'ORG','name':'Analytics Org'}).json();site=client.post('/api/v1/sites',headers=h,json={'organization_id':org['id'],'code':'S','name':'Site'}).json();plant=client.post('/api/v1/plants',headers=h,json={'site_id':site['id'],'code':'P','name':'Plant'}).json();sec=client.post('/api/v1/sectors',headers=h,json={'plant_id':plant['id'],'code':'SEC','name':'Sector'}).json();cam=client.post('/api/v1/cameras',headers=h,json={'sector_id':sec['id'],'code':code+'CAM','name':'Cam','source_type':'DEMO_FILE','capture_fps':5}).json();zone=client.post('/api/v1/zones',headers=h,json={'camera_id':cam['id'],'code':'Z','name':'Zone','polygon_points':[{'x':.1,'y':.1},{'x':.9,'y':.1},{'x':.9,'y':.9},{'x':.1,'y':.9}]}).json()
 with SessionLocal() as db:
  camera=db.get(Camera,uuid.UUID(cam['id']));ppe=db.scalar(select(PPEType).where(PPEType.code=='HELMET'));z=db.get(Zone,uuid.UUID(zone['id']));now=datetime.now(timezone.utc);action={'type':'OPEN','key':f'{camera.id}:TRACK-8:HELMET','track_id':'TRACK-8','rule':{'zone_id':str(z.id),'ppe_type_id':str(ppe.id),'ppe_code':'HELMET','ppe_name':ppe.name,'requirement':'REQUIRED','severity':severity},'observed_status':'NO_DETECTADO','confidence':.2,'missing_span_seconds':2,'consensus_ratio':1.0,'missing_observations':3,'evaluable_observations':3};ev,_=open_or_get_event(db,camera,action,{'engine_version':'0.9.0'},15,now);db.commit();eid=str(ev.id)
 return org,cam,zone,eid

def test_analytics_permissions_seeded():
 with SessionLocal() as db:
  assert db.scalar(select(Permission).where(Permission.code=='analytics.read'));assert db.scalar(select(Permission).where(Permission.code=='analytics.export'))
  assert 'analytics.read' in {p.code for p in db.scalar(select(Role).where(Role.code=='CONSULTA')).permissions}

def test_executive_trend_risks_heatmap_and_csv(client,admin_headers):
 org,cam,zone,eid=make_event(client,admin_headers,'KPI')
 q=f'?organization_id={org["id"]}&include_qa=true'
 r=client.get('/api/v1/analytics/executive'+q,headers=admin_headers);assert r.status_code==200 and r.json()['total_events']>=1
 assert client.get('/api/v1/analytics/trend'+q,headers=admin_headers).status_code==200
 assert client.get('/api/v1/analytics/top-risks'+q+'&dimension=ppe',headers=admin_headers).json()[0]['count']>=1
 hm=client.get('/api/v1/analytics/heatmap'+q+f'&camera_id={cam["id"]}',headers=admin_headers);assert hm.status_code==200 and any(x['zone_id']==zone['id'] for x in hm.json())
 csv=client.get('/api/v1/analytics/export.csv'+q,headers=admin_headers);assert csv.status_code==200 and 'event_number' in csv.text and 'HYS-' in csv.text

def test_cleanup_archives_without_deleting_evidence_or_actions_and_restores_sla(client,admin_headers):
 org,cam,zone,eid=make_event(client,admin_headers,'CLEAN')
 with SessionLocal() as db:
  o=db.get(Organization,uuid.UUID(org['id']));pol=list(db.scalars(select(AlertPolicy).where(AlertPolicy.organization_id==o.id)));
  for p in pol:p.acknowledge_sla_seconds=20
  db.commit();r=cleanup_pilot(db,o,None,'QA cleanup test');ev=db.get(SafetyDetectionEvent,uuid.UUID(eid));assert r.archived_events>=1 and ev.archived_at and ev.analytics_excluded and ev.data_origin=='QA_PILOT' and ev.operational_status=='RESOLVED';assert all(p.acknowledge_sla_seconds in (300,120,60) for p in db.scalars(select(AlertPolicy).where(AlertPolicy.organization_id==o.id)))
 r=client.get(f'/api/v1/analytics/executive?organization_id={org["id"]}',headers=admin_headers);assert r.status_code==200 and r.json()['total_events']==0 and r.json()['archived_qa_events']>=1
 r=client.get(f'/api/v1/monitoring/inbox?organization_id={org["id"]}',headers=admin_headers);assert r.status_code==200

def test_report_endpoint(client,admin_headers):
 org,_,_,_=make_event(client,admin_headers,'REP');r=client.get(f'/api/v1/analytics/report?organization_id={org["id"]}&include_qa=true',headers=admin_headers);assert r.status_code==200 and r.json()['title'].startswith('Informe Ejecutivo')
