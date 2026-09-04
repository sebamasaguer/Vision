import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.access import Permission, Role, User
from app.models.camera import Camera
from app.models.safety import (
    AlertEscalation, AlertPolicy, NotificationChannel, NotificationDelivery,
    PPEType, SafetyDetectionEvent, Zone,
)
from app.services.alerting import process_alerts, recompute_event_sla
from app.services.safety_events import open_or_get_event


def create_event(client, headers, code='B7', severity='ALTA'):
    org=client.post('/api/v1/organizations',headers=headers,json={'code':code+'ORG','name':'Block7 Org'}).json()
    site=client.post('/api/v1/sites',headers=headers,json={'organization_id':org['id'],'code':'S','name':'Site'}).json()
    plant=client.post('/api/v1/plants',headers=headers,json={'site_id':site['id'],'code':'P','name':'Plant'}).json()
    sec=client.post('/api/v1/sectors',headers=headers,json={'plant_id':plant['id'],'code':'SEC','name':'Sector'}).json()
    cam=client.post('/api/v1/cameras',headers=headers,json={'sector_id':sec['id'],'code':code+'CAM','name':'Cam','source_type':'DEMO_FILE','capture_fps':5}).json()
    zone=client.post('/api/v1/zones',headers=headers,json={'camera_id':cam['id'],'code':'Z','name':'Zone','polygon_points':[{'x':.1,'y':.1},{'x':.9,'y':.1},{'x':.9,'y':.9},{'x':.1,'y':.9}]}).json()
    with SessionLocal() as db:
        camera=db.get(Camera,uuid.UUID(cam['id']));ppe=db.scalar(select(PPEType).where(PPEType.code=='HELMET'));z=db.get(Zone,uuid.UUID(zone['id']));now=datetime.now(timezone.utc)
        action={'type':'OPEN','key':f'{camera.id}:TRACK-0001:HELMET','track_id':'TRACK-0001','rule':{'zone_id':str(z.id),'ppe_type_id':str(ppe.id),'ppe_code':'HELMET','ppe_name':ppe.name,'requirement':'REQUIRED','severity':severity},'observed_status':'NO_DETECTADO','confidence':.2,'missing_span_seconds':2,'consensus_ratio':1.0,'missing_observations':3,'evaluable_observations':3}
        ev,_=open_or_get_event(db,camera,action,{'engine_version':'0.8.0'},15,now);db.commit();eid=str(ev.id)
    return org,cam,eid


def test_event_initializes_sla_policy_channels_and_in_app_delivery(client,admin_headers):
    org,_,eid=create_event(client,admin_headers,'INIT','ALTA')
    with SessionLocal() as db:
        ev=db.get(SafetyDetectionEvent,uuid.UUID(eid));assert ev.alert_priority=='P1_ALTA';assert ev.sla_ack_due_at and ev.sla_resolve_due_at;assert ev.ack_sla_status=='PENDING';assert ev.resolve_sla_status=='PENDING'
        policies=list(db.scalars(select(AlertPolicy).where(AlertPolicy.organization_id==uuid.UUID(org['id']))));assert {x.severity for x in policies}=={'ADVERTENCIA','ALTA','CRITICA'}
        channels=list(db.scalars(select(NotificationChannel).where(NotificationChannel.organization_id==uuid.UUID(org['id']))));assert {x.channel for x in channels}=={'IN_APP','EMAIL','WEBHOOK','WHATSAPP'}
        deliveries=list(db.scalars(select(NotificationDelivery).where(NotificationDelivery.event_id==ev.id)));assert len(deliveries)==1;assert deliveries[0].channel=='IN_APP' and deliveries[0].status=='DELIVERED'


def test_default_sla_values_by_severity(client,admin_headers):
    for code,severity,ack,res in [('W','ADVERTENCIA',300,1800),('H','ALTA',120,900),('C','CRITICA',60,600)]:
        _,_,eid=create_event(client,admin_headers,'S'+code,severity)
        with SessionLocal() as db:
            ev=db.get(SafetyDetectionEvent,uuid.UUID(eid));base=ev.confirmed_at.replace(tzinfo=timezone.utc) if ev.confirmed_at.tzinfo is None else ev.confirmed_at
            ack_due=ev.sla_ack_due_at.replace(tzinfo=timezone.utc) if ev.sla_ack_due_at.tzinfo is None else ev.sla_ack_due_at
            res_due=ev.sla_resolve_due_at.replace(tzinfo=timezone.utc) if ev.sla_resolve_due_at.tzinfo is None else ev.sla_resolve_due_at
            assert round((ack_due-base).total_seconds())==ack;assert round((res_due-base).total_seconds())==res


def test_process_before_due_does_not_escalate(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'NODUE')
    with SessionLocal() as db:
        ev=db.get(SafetyDetectionEvent,uuid.UUID(eid));now=(ev.confirmed_at.replace(tzinfo=timezone.utc) if ev.confirmed_at.tzinfo is None else ev.confirmed_at)+timedelta(seconds=10);r=process_alerts(db,now,send_external=False);assert r['escalated']==0;db.refresh(ev);assert ev.escalation_level==0


def test_ack_sla_breach_escalates_once_and_dedupes(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'BREACH','CRITICA')
    with SessionLocal() as db:
        ev=db.get(SafetyDetectionEvent,uuid.UUID(eid));base=ev.confirmed_at.replace(tzinfo=timezone.utc) if ev.confirmed_at.tzinfo is None else ev.confirmed_at;ev.sla_ack_due_at=base+timedelta(seconds=1);ev.next_escalation_at=base+timedelta(seconds=1);db.commit();r=process_alerts(db,base+timedelta(seconds=2),send_external=False);assert r['ack_breached']==1 and r['escalated']==1;db.refresh(ev);assert ev.ack_sla_status=='BREACHED' and ev.escalation_level==1
        assert db.scalar(select(AlertEscalation).where(AlertEscalation.event_id==ev.id,AlertEscalation.level==1))
        count1=len(list(db.scalars(select(NotificationDelivery).where(NotificationDelivery.event_id==ev.id))))
        process_alerts(db,base+timedelta(seconds=3),send_external=False);count2=len(list(db.scalars(select(NotificationDelivery).where(NotificationDelivery.event_id==ev.id))));assert count2==count1


def test_escalation_repeats_until_policy_max(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'MAX','CRITICA')
    with SessionLocal() as db:
        ev=db.get(SafetyDetectionEvent,uuid.UUID(eid));pol=db.scalar(select(AlertPolicy).where(AlertPolicy.organization_id==ev.organization_id,AlertPolicy.severity=='CRITICA'));pol.escalation_repeat_seconds=1;pol.max_escalation_level=2;base=ev.confirmed_at.replace(tzinfo=timezone.utc) if ev.confirmed_at.tzinfo is None else ev.confirmed_at;ev.next_escalation_at=base;db.commit();process_alerts(db,base+timedelta(seconds=1),send_external=False);process_alerts(db,base+timedelta(seconds=3),send_external=False);process_alerts(db,base+timedelta(seconds=5),send_external=False);db.refresh(ev);assert ev.escalation_level==2 and ev.next_escalation_at is None
        assert len(list(db.scalars(select(AlertEscalation).where(AlertEscalation.event_id==ev.id))))==2


def test_acknowledge_before_due_marks_sla_met(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'ACK')
    r=client.post(f'/api/v1/safety-events/{eid}/acknowledge',headers=admin_headers);assert r.status_code==200;assert r.json()['ack_sla_status']=='MET'


def test_late_ack_keeps_breach(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'LATE')
    with SessionLocal() as db:
        ev=db.get(SafetyDetectionEvent,uuid.UUID(eid));ev.sla_ack_due_at=datetime.now(timezone.utc)-timedelta(seconds=2);db.commit()
    r=client.post(f'/api/v1/safety-events/{eid}/acknowledge',headers=admin_headers);assert r.status_code==200;assert r.json()['ack_sla_status']=='BREACHED'


def test_operational_resolve_stops_escalation_and_marks_resolution_met(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'RES')
    r=client.post(f'/api/v1/safety-events/{eid}/resolve',headers=admin_headers,json={'note':'Condición atendida'});assert r.status_code==200;b=r.json();assert b['resolve_sla_status']=='MET' and b['next_escalation_at'] is None


def test_monitoring_summary_and_inbox_wrapped_response(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'API')
    s=client.get('/api/v1/monitoring/summary',headers=admin_headers);assert s.status_code==200;assert s.json()['active']>=1 and s.json()['unacknowledged']>=1
    r=client.get('/api/v1/monitoring/inbox',headers=admin_headers);assert r.status_code==200;b=r.json();assert isinstance(b['items'],list) and b['total']>=1;item=next(x for x in b['items'] if x['event_id']==eid);assert item['priority']=='P1_ALTA' and item['notification_count']>=1


def test_monitoring_overdue_filter(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'FILT')
    with SessionLocal() as db:
        ev=db.get(SafetyDetectionEvent,uuid.UUID(eid));ev.sla_ack_due_at=datetime.now(timezone.utc)-timedelta(seconds=5);recompute_event_sla(ev);db.commit()
    r=client.get('/api/v1/monitoring/inbox?sla=ACK_OVERDUE',headers=admin_headers);assert r.status_code==200;assert eid in {x['event_id'] for x in r.json()['items']}


def test_policy_api_update(client,admin_headers):
    _,_,_=create_event(client,admin_headers,'POL')
    rows=client.get('/api/v1/monitoring/policies',headers=admin_headers).json()['items'];alta=next(x for x in rows if x['severity']=='ALTA')
    r=client.patch(f"/api/v1/monitoring/policies/{alta['id']}",headers=admin_headers,json={'acknowledge_sla_seconds':90,'max_escalation_level':5});assert r.status_code==200;assert r.json()['acknowledge_sla_seconds']==90 and r.json()['max_escalation_level']==5


def test_in_app_channel_cannot_be_disabled(client,admin_headers):
    _,_,_=create_event(client,admin_headers,'CH1')
    rows=client.get('/api/v1/monitoring/channels',headers=admin_headers).json()['items'];c=next(x for x in rows if x['channel']=='IN_APP')
    r=client.patch(f"/api/v1/monitoring/channels/{c['id']}",headers=admin_headers,json={'enabled':False});assert r.status_code==422


def test_webhook_channel_ready_with_destination(client,admin_headers):
    _,_,_=create_event(client,admin_headers,'CH2')
    rows=client.get('/api/v1/monitoring/channels',headers=admin_headers).json()['items'];c=next(x for x in rows if x['channel']=='WEBHOOK')
    r=client.patch(f"/api/v1/monitoring/channels/{c['id']}",headers=admin_headers,json={'enabled':True,'destination':'https://alerts.example.invalid/hys'});assert r.status_code==200;assert r.json()['configuration_status']=='READY'


def test_email_without_smtp_remains_config_required(client,admin_headers):
    _,_,_=create_event(client,admin_headers,'CH3')
    rows=client.get('/api/v1/monitoring/channels',headers=admin_headers).json()['items'];c=next(x for x in rows if x['channel']=='EMAIL')
    r=client.patch(f"/api/v1/monitoring/channels/{c['id']}",headers=admin_headers,json={'enabled':True,'destination':'hys@example.com'});assert r.status_code==200;assert r.json()['configuration_status']=='CONFIG_REQUIRED'


def test_deliveries_endpoint_uses_wrapper(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'DEL')
    r=client.get('/api/v1/monitoring/deliveries',headers=admin_headers);assert r.status_code==200;b=r.json();assert isinstance(b['items'],list) and any(x['event_id']==eid for x in b['items'])


def test_escalations_endpoint(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'ESC')
    with SessionLocal() as db:
        ev=db.get(SafetyDetectionEvent,uuid.UUID(eid));base=datetime.now(timezone.utc);ev.next_escalation_at=base-timedelta(seconds=1);db.commit();process_alerts(db,base,send_external=False)
    r=client.get(f'/api/v1/monitoring/events/{eid}/escalations',headers=admin_headers);assert r.status_code==200 and r.json()['total']==1


def test_process_once_endpoint(client,admin_headers):
    create_event(client,admin_headers,'ONCE');r=client.post('/api/v1/monitoring/process-once',headers=admin_headers);assert r.status_code==200 and r.json()['processed']>=1


def test_monitoring_permissions_seeded():
    with SessionLocal() as db:
        assert db.scalar(select(Permission).where(Permission.code=='monitoring.read'))
        assert db.scalar(select(Permission).where(Permission.code=='monitoring.manage'))
        for code in ['SUPERADMIN','ADMIN_EMPRESA','RESPONSABLE_HYS','OPERADOR_MONITOREO']:
            role=db.scalar(select(Role).where(Role.code==code));codes={p.code for p in role.permissions};assert {'monitoring.read','monitoring.manage'}<=codes
        for code in ['AUDITOR','CONSULTA']:
            role=db.scalar(select(Role).where(Role.code==code));codes={p.code for p in role.permissions};assert 'monitoring.read' in codes and 'monitoring.manage' not in codes


def test_monitoring_tenant_isolation(client,admin_headers):
    org1,_,eid1=create_event(client,admin_headers,'T1')
    create_event(client,admin_headers,'T2')
    u=client.post('/api/v1/users',headers=admin_headers,json={'organization_id':org1['id'],'email':'monitor@example.org','full_name':'Monitor Tenant','password':'Password-12345!','role_codes':['OPERADOR_MONITOREO']});assert u.status_code==201
    login=client.post('/api/v1/auth/login',json={'email':'monitor@example.org','password':'Password-12345!'});h={'Authorization':f"Bearer {login.json()['access_token']}"}
    r=client.get('/api/v1/monitoring/inbox',headers=h);assert r.status_code==200;ids={x['event_id'] for x in r.json()['items']};assert eid1 in ids and len(ids)==1


def test_legacy_unresolved_event_gets_sla_grace_from_block7_activation(client,admin_headers):
    _,_,eid=create_event(client,admin_headers,'LEGACY','ALTA')
    now=datetime.now(timezone.utc)
    with SessionLocal() as db:
        ev=db.get(SafetyDetectionEvent,uuid.UUID(eid));ev.confirmed_at=now-timedelta(days=1);ev.sla_ack_due_at=None;ev.sla_resolve_due_at=None;ev.next_escalation_at=None;ev.escalation_level=0;ev.last_escalated_at=None;db.commit();process_alerts(db,now,send_external=False);db.refresh(ev)
        ack=ev.sla_ack_due_at.replace(tzinfo=timezone.utc) if ev.sla_ack_due_at.tzinfo is None else ev.sla_ack_due_at
        assert 115 <= (ack-now).total_seconds() <= 125
        assert ev.ack_sla_status=='PENDING' and ev.escalation_level==0
