from datetime import datetime, timedelta, timezone

from app.services.compliance_runtime import TemporalComplianceEngine, compliance_status, effective_rules_for_track

BASE = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
POLICY = {
    'window_seconds': 4.0,
    'min_persistence_seconds': 2.0,
    'min_consensus_ratio': .70,
    'min_missing_observations': 3,
    'cooldown_seconds': 5.0,
    'clear_grace_seconds': 1.0,
    'track_absence_close_seconds': 2.0,
}
RULE = {
    'id':'r1','zone_id':'z1','zone_code':'Z1','ppe_type_id':'p1','ppe_code':'HELMET','ppe_name':'Casco',
    'requirement':'REQUIRED','severity':'ALTA','min_confidence':.70,'active':True,
    'schedule_start':None,'schedule_end':None,
}

def track(status='OK', conf=.9, zones=True, detected=None):
    if detected is None: detected = status == 'OK'
    return {'track_id':'TRACK-0001','zones':[{'id':'z1','code':'Z1','name':'Zona'}] if zones else [],
            'ppe':{'HELMET':{'status':status,'confidence':conf,'detected':detected,'visible_ratio':1.0}}}

def at(sec): return BASE + timedelta(seconds=sec)


def test_status_mapping_preserves_unknown_and_no_aplica():
    assert compliance_status('OK') == 'COMPLIANT'
    assert compliance_status('NO_DETECTADO') == 'NON_COMPLIANT'
    assert compliance_status('NO_VISIBLE') == 'UNKNOWN'
    assert compliance_status('INCIERTO') == 'UNKNOWN'
    assert compliance_status('NO_DETECTADO','OPTIONAL') == 'NO_APLICA'


def test_ok_person_does_not_open_event():
    e=TemporalComplianceEngine('cam',POLICY)
    for i in range(5):
        r=e.evaluate([track('OK')],[RULE],at(i))
        assert not [a for a in r['actions'] if a['type']=='OPEN']


def test_persistent_missing_opens_only_after_temporal_threshold():
    e=TemporalComplianceEngine('cam',POLICY)
    assert not e.evaluate([track('NO_DETECTADO',.2,detected=False)],[RULE],at(0))['actions']
    assert not e.evaluate([track('NO_DETECTADO',.2,detected=False)],[RULE],at(1))['actions']
    actions=e.evaluate([track('NO_DETECTADO',.2,detected=False)],[RULE],at(2))['actions']
    assert len(actions)==1 and actions[0]['type']=='OPEN'
    assert actions[0]['missing_observations']==3 and actions[0]['consensus_ratio']==1.0


def test_no_visible_breaks_persistence_and_never_opens_event():
    e=TemporalComplianceEngine('cam',POLICY)
    e.evaluate([track('NO_DETECTADO',.2,detected=False)],[RULE],at(0))
    e.evaluate([track('NO_VISIBLE',None,detected=False)],[RULE],at(1))
    e.evaluate([track('NO_DETECTADO',.2,detected=False)],[RULE],at(2))
    r=e.evaluate([track('NO_DETECTADO',.2,detected=False)],[RULE],at(3))
    assert not [a for a in r['actions'] if a['type']=='OPEN']
    assert r['tracks']['TRACK-0001'][0]['missing_observations']==2


def test_person_outside_zone_rule_does_not_apply():
    e=TemporalComplianceEngine('cam',POLICY)
    r=e.evaluate([track('NO_DETECTADO',.2,zones=False,detected=False)],[RULE],at(0))
    assert r['tracks']['TRACK-0001']==[] and r['actions']==[]


def test_same_track_missing_produces_one_open_then_updates():
    e=TemporalComplianceEngine('cam',POLICY)
    for i in [0,1]: e.evaluate([track('NO_DETECTADO',.2,detected=False)],[RULE],at(i))
    r=e.evaluate([track('NO_DETECTADO',.2,detected=False)],[RULE],at(2)); assert r['actions'][0]['type']=='OPEN'
    key=r['actions'][0]['key']; e.bind_event(key,'11111111-1111-1111-1111-111111111111')
    r=e.evaluate([track('NO_DETECTADO',.2,detected=False)],[RULE],at(3))
    assert [a['type'] for a in r['actions']]==['UPDATE']


def test_condition_clear_closes_after_grace():
    e=TemporalComplianceEngine('cam',POLICY)
    for i in [0,1]: e.evaluate([track('NO_DETECTADO',.2,detected=False)],[RULE],at(i))
    r=e.evaluate([track('NO_DETECTADO',.2,detected=False)],[RULE],at(2)); key=r['actions'][0]['key']; e.bind_event(key,'11111111-1111-1111-1111-111111111111')
    assert not e.evaluate([track('OK')],[RULE],at(3))['actions']
    actions=e.evaluate([track('OK')],[RULE],at(4.1))['actions']
    assert actions[0]['type']=='CLOSE' and actions[0]['reason']=='CONDITION_CLEARED'


def test_track_absence_closes_active_event():
    e=TemporalComplianceEngine('cam',POLICY)
    for i in [0,1]: e.evaluate([track('NO_DETECTADO',.2,detected=False)],[RULE],at(i))
    r=e.evaluate([track('NO_DETECTADO',.2,detected=False)],[RULE],at(2)); key=r['actions'][0]['key']; e.bind_event(key,'11111111-1111-1111-1111-111111111111')
    assert not e.evaluate([], [RULE], at(3))['actions']
    actions=e.evaluate([], [RULE], at(4.1))['actions']
    assert actions[0]['type']=='CLOSE' and actions[0]['reason']=='TRACK_ABSENT'


def test_cooldown_suppresses_immediate_reopen():
    e=TemporalComplianceEngine('cam',POLICY)
    for i in [0,1]: e.evaluate([track('NO_DETECTADO',.2,detected=False)],[RULE],at(i))
    r=e.evaluate([track('NO_DETECTADO',.2,detected=False)],[RULE],at(2)); key=r['actions'][0]['key']; e.bind_event(key,'11111111-1111-1111-1111-111111111111')
    e.mark_closed(key,at(3))
    for i in [4,5,6,7]:
        assert not [a for a in e.evaluate([track('NO_DETECTADO',.2,detected=False)],[RULE],at(i))['actions'] if a['type']=='OPEN']
    # cooldown termina en t=8; tres observaciones consecutivas nuevas permiten reapertura.
    r=e.evaluate([track('NO_DETECTADO',.2,detected=False)],[RULE],at(8))
    assert [a for a in r['actions'] if a['type']=='OPEN']


def test_unsupported_ppe_rule_becomes_no_aplica_not_violation():
    e=TemporalComplianceEngine('cam',POLICY)
    rule={**RULE,'ppe_code':'GOGGLES','ppe_name':'Gafas','ppe_type_id':'p2'}
    r=e.evaluate([track('OK')],[rule],at(0))
    item=r['tracks']['TRACK-0001'][0]
    assert item['observed_status']=='NO_APLICA' and item['compliance_status']=='NO_APLICA' and r['actions']==[]


def test_overlapping_zones_choose_highest_required_severity_per_ppe():
    t=track('NO_DETECTADO',.2,detected=False); t['zones'].append({'id':'z2','code':'Z2','name':'Zona2'})
    rules=[RULE,{**RULE,'id':'r2','zone_id':'z2','zone_code':'Z2','severity':'CRITICA'}]
    picked=effective_rules_for_track(t,rules,BASE,'America/Argentina/Salta')
    assert len(picked)==1 and picked[0]['severity']=='CRITICA'


def test_rule_confidence_can_turn_low_positive_into_uncertain():
    e=TemporalComplianceEngine('cam',POLICY)
    strict={**RULE,'min_confidence':.95}
    r=e.evaluate([track('OK',.80,detected=True)],[strict],at(0))
    item=r['tracks']['TRACK-0001'][0]
    assert item['observed_status']=='INCIERTO' and item['compliance_status']=='UNKNOWN'


def test_safety_events_api_empty_and_summary(client,admin_headers):
    r=client.get('/api/v1/safety-events',headers=admin_headers)
    assert r.status_code==200 and r.json()==[]
    s=client.get('/api/v1/safety-events/summary',headers=admin_headers)
    assert s.status_code==200 and s.json()['active']==0 and s.json()['total']==0


def test_vision_settings_expose_compliance_controls(client,admin_headers):
    o=client.post('/api/v1/organizations',headers=admin_headers,json={'code':'CMPORG','name':'Compliance Org'}).json()
    si=client.post('/api/v1/sites',headers=admin_headers,json={'organization_id':o['id'],'code':'S','name':'Site'}).json()
    pl=client.post('/api/v1/plants',headers=admin_headers,json={'site_id':si['id'],'code':'P','name':'Plant'}).json()
    sec=client.post('/api/v1/sectors',headers=admin_headers,json={'plant_id':pl['id'],'code':'SEC','name':'Sector'}).json()
    cam=client.post('/api/v1/cameras',headers=admin_headers,json={'sector_id':sec['id'],'code':'CMPCAM','name':'Compliance Camera','source_type':'DEMO_FILE','capture_fps':5}).json()
    body=client.get(f"/api/v1/vision/cameras/{cam['id']}/settings",headers=admin_headers).json()
    assert body['compliance_enabled'] is False and body['compliance_min_consensus_ratio']==.70
    p=client.patch(f"/api/v1/vision/cameras/{cam['id']}/settings",headers=admin_headers,json={'compliance_enabled':True,'compliance_min_persistence_seconds':2.5})
    assert p.status_code==200 and p.json()['compliance_enabled'] is True


def test_event_repository_persists_dedupes_and_closes(client,admin_headers):
    import uuid
    from app.db.session import SessionLocal
    from app.models.camera import Camera
    from app.models.safety import PPEType, Zone
    from app.services.safety_events import close_event, open_or_get_event, update_event
    from sqlalchemy import select

    o=client.post('/api/v1/organizations',headers=admin_headers,json={'code':'EVORG','name':'Events Org'}).json()
    si=client.post('/api/v1/sites',headers=admin_headers,json={'organization_id':o['id'],'code':'S','name':'Site'}).json()
    pl=client.post('/api/v1/plants',headers=admin_headers,json={'site_id':si['id'],'code':'P','name':'Plant'}).json()
    sec=client.post('/api/v1/sectors',headers=admin_headers,json={'plant_id':pl['id'],'code':'SEC','name':'Sector'}).json()
    cam_body=client.post('/api/v1/cameras',headers=admin_headers,json={'sector_id':sec['id'],'code':'EVCAM','name':'Event Camera','source_type':'DEMO_FILE','capture_fps':5}).json()
    zone_body=client.post('/api/v1/zones',headers=admin_headers,json={'camera_id':cam_body['id'],'code':'EVZ','name':'Event Zone','polygon_points':[{'x':.1,'y':.1},{'x':.9,'y':.1},{'x':.9,'y':.9},{'x':.1,'y':.9}]}).json()
    now=datetime.now(timezone.utc)
    with SessionLocal() as db:
        cam=db.get(Camera,uuid.UUID(cam_body['id'])); ppe=db.scalar(select(PPEType).where(PPEType.code=='HELMET')); zone=db.get(Zone,uuid.UUID(zone_body['id']))
        action={'type':'OPEN','key':f"{cam.id}:TRACK-0001:HELMET",'track_id':'TRACK-0001','rule':{'zone_id':str(zone.id),'zone_code':zone.code,'ppe_type_id':str(ppe.id),'ppe_code':'HELMET','ppe_name':ppe.name,'requirement':'REQUIRED','severity':'ALTA','min_confidence':.7},'observed_status':'NO_DETECTADO','confidence':.2,'missing_span_seconds':2,'consensus_ratio':1.0,'missing_observations':3,'evaluable_observations':3}
        ev,_=open_or_get_event(db,cam,action,{'engine_version':'0.6.0'},15,now); db.commit(); first_id=ev.id
        ev2,_=open_or_get_event(db,cam,action,{'engine_version':'0.6.0'},15,now+timedelta(seconds=1)); assert ev2.id==first_id
        update_event(ev2,{**action,'missing_span_seconds':3,'missing_observations':4,'evaluable_observations':4},now+timedelta(seconds=1)); close_event(ev2,now+timedelta(seconds=2),'CONDITION_CLEARED'); db.commit()
    rows=client.get('/api/v1/safety-events?status=CLOSED',headers=admin_headers).json()
    assert len(rows)==1 and rows[0]['id']==str(first_id) and rows[0]['close_reason']=='CONDITION_CLEARED'
    summary=client.get('/api/v1/safety-events/summary',headers=admin_headers)
    assert summary.status_code==200
    assert summary.json()['closed_today']==1 and summary.json()['total']==1
