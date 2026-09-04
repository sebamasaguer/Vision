from datetime import datetime, timedelta, timezone
from app.services.compliance_runtime import TemporalComplianceEngine

base=datetime.now(timezone.utc)
policy={'window_seconds':4.0,'min_persistence_seconds':2.0,'min_consensus_ratio':.70,'min_missing_observations':3,'cooldown_seconds':5.0,'clear_grace_seconds':1.0,'track_absence_close_seconds':2.0}
rule={'id':'qa-rule','zone_id':'qa-zone','zone_code':'QA','ppe_type_id':'qa-ppe','ppe_code':'HELMET','ppe_name':'Casco','requirement':'REQUIRED','severity':'ALTA','min_confidence':.70,'active':True,'schedule_start':None,'schedule_end':None}
def tr(status,detected=None):
    if detected is None: detected=status=='OK'
    return {'track_id':'TRACK-QA','zones':[{'id':'qa-zone','code':'QA','name':'QA'}],'ppe':{'HELMET':{'status':status,'confidence':.2 if status=='NO_DETECTADO' else .9,'detected':detected,'visible_ratio':1.0}}}
def ts(n): return base+timedelta(seconds=n)

# Caso conforme
e=TemporalComplianceEngine('qa-camera',policy)
assert not e.evaluate([tr('OK')],[rule],ts(0))['actions']
print('[PASS] Persona + casco -> NO EVENTO')
# Persistencia
e=TemporalComplianceEngine('qa-camera',policy)
e.evaluate([tr('NO_DETECTADO',False)],[rule],ts(0)); e.evaluate([tr('NO_DETECTADO',False)],[rule],ts(1))
a=e.evaluate([tr('NO_DETECTADO',False)],[rule],ts(2))['actions']; assert len(a)==1 and a[0]['type']=='OPEN'
print('[PASS] Persona sin casco persistente -> EVENTO tras persistencia/consenso')
# Oclusión rompe persistencia
e=TemporalComplianceEngine('qa-camera',policy)
e.evaluate([tr('NO_DETECTADO',False)],[rule],ts(0)); e.evaluate([tr('NO_VISIBLE',False)],[rule],ts(1)); e.evaluate([tr('NO_DETECTADO',False)],[rule],ts(2)); a=e.evaluate([tr('NO_DETECTADO',False)],[rule],ts(3))['actions']; assert not a
print('[PASS] NO_VISIBLE interrumpe persistencia -> NO EVENTO')
# Dedupe
e=TemporalComplianceEngine('qa-camera',policy)
e.evaluate([tr('NO_DETECTADO',False)],[rule],ts(0)); e.evaluate([tr('NO_DETECTADO',False)],[rule],ts(1)); a=e.evaluate([tr('NO_DETECTADO',False)],[rule],ts(2))['actions']; key=a[0]['key']; e.bind_event(key,'00000000-0000-0000-0000-000000000001'); a=e.evaluate([tr('NO_DETECTADO',False)],[rule],ts(3))['actions']; assert [x['type'] for x in a]==['UPDATE']
print('[PASS] Mismo track + EPP -> UPDATE del mismo evento, no duplicado')
print('[PASS] MOTOR CUMPLIMIENTO v0.6.0 QA')
