import hashlib
import io
import uuid
from sqlalchemy import inspect, select
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.access import Permission, Role


def main():
    with SessionLocal() as db:
        i=inspect(db.bind)
        tables=set(i.get_table_names())
        required={'safety_detection_events','safety_event_evidence','safety_event_notes','safety_event_actions'}
        assert required <= tables, required-tables
        cols={c['name'] for c in i.get_columns('safety_detection_events')}
        need={'operational_status','review_outcome','assigned_to_user_id','acknowledged_at','reviewed_at','resolved_at','evidence_status','evidence_count','evidence_captured_at'}
        assert need <= cols, need-cols
        assert db.scalar(select(Permission).where(Permission.code=='safety_event.manage'))
        for code in ['SUPERADMIN','ADMIN_EMPRESA','RESPONSABLE_HYS','OPERADOR_MONITOREO']:
            role=db.scalar(select(Role).where(Role.code==code)); assert role and 'safety_event.manage' in {p.code for p in role.permissions}
        for code in ['AUDITOR','CONSULTA']:
            role=db.scalar(select(Role).where(Role.code==code)); assert role and 'safety_event.manage' not in {p.code for p in role.permissions}

    from minio import Minio
    client=Minio(settings.minio_endpoint,access_key=settings.minio_access_key,secret_key=settings.minio_secret_key,secure=settings.minio_secure)
    assert client.bucket_exists(settings.minio_bucket_evidence)
    payload=b'HYS Vision IA Block 6 evidence storage QA\n'
    digest=hashlib.sha256(payload).hexdigest(); key=f'qa/block6/{uuid.uuid4().hex}.txt'
    client.put_object(settings.minio_bucket_evidence,key,io.BytesIO(payload),len(payload),content_type='text/plain')
    response=client.get_object(settings.minio_bucket_evidence,key)
    try: read=response.read()
    finally: response.close(); response.release_conn()
    assert hashlib.sha256(read).hexdigest()==digest
    client.remove_object(settings.minio_bucket_evidence,key)
    print('BLOCK6_SCHEMA_OK',','.join(sorted(required)))
    print('BLOCK6_EVENT_COLUMNS_OK',len(need))
    print('BLOCK6_RBAC_OK safety_event.manage')
    print('BLOCK6_MINIO_ROUNDTRIP_OK sha256='+digest[:16])

if __name__=='__main__': main()
