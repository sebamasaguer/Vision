from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import inspect, select

from app.db.session import SessionLocal, engine
from app.models.access import Permission, Role
from app.models.organization import Organization
from app.models.safety import (
    AlertPolicy, NotificationChannel, SafetyDetectionEvent,
)
from app.services.alerting import (
    ensure_alert_policies, ensure_notification_channels, initialize_event_alert_state,
    process_alerts,
)

REQUIRED_TABLES = {
    'alert_escalations','alert_policies','notification_channels','notification_deliveries'
}
REQUIRED_EVENT_COLUMNS = {
    'alert_priority','sla_ack_due_at','sla_resolve_due_at','ack_sla_status',
    'resolve_sla_status','escalation_level','next_escalation_at','last_escalated_at',
    'last_notification_at'
}


def main() -> None:
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    missing = REQUIRED_TABLES - tables
    if missing:
        raise SystemExit(f'BLOCK7_SCHEMA_FAIL missing={sorted(missing)}')
    print('BLOCK7_SCHEMA_OK ' + ','.join(sorted(REQUIRED_TABLES)))

    cols = {c['name'] for c in insp.get_columns('safety_detection_events')}
    missing_cols = REQUIRED_EVENT_COLUMNS - cols
    if missing_cols:
        raise SystemExit(f'BLOCK7_EVENT_COLUMNS_FAIL missing={sorted(missing_cols)}')
    print(f'BLOCK7_EVENT_COLUMNS_OK {len(REQUIRED_EVENT_COLUMNS)}')

    with SessionLocal() as db:
        for code in ('monitoring.read','monitoring.manage'):
            if not db.scalar(select(Permission).where(Permission.code == code)):
                raise SystemExit(f'BLOCK7_RBAC_FAIL missing={code}')
        for role_code in ('SUPERADMIN','ADMIN_EMPRESA','RESPONSABLE_HYS','OPERADOR_MONITOREO'):
            role = db.scalar(select(Role).where(Role.code == role_code))
            if role is None:
                raise SystemExit(f'BLOCK7_RBAC_FAIL role={role_code}')
            codes = {p.code for p in role.permissions}
            if not {'monitoring.read','monitoring.manage'} <= codes:
                raise SystemExit(f'BLOCK7_RBAC_FAIL role={role_code} codes={sorted(codes)}')
        print('BLOCK7_RBAC_OK monitoring.read,monitoring.manage')

        orgs = list(db.scalars(select(Organization).where(Organization.active.is_(True))))
        if not orgs:
            raise SystemExit('BLOCK7_POLICY_FAIL no_organizations')
        for org in orgs:
            policies = ensure_alert_policies(db, org.id)
            channels = ensure_notification_channels(db, org.id)
            pmap = {p.severity: p for p in policies}
            if set(pmap) != {'ADVERTENCIA','ALTA','CRITICA'}:
                raise SystemExit(f'BLOCK7_POLICY_FAIL org={org.code}')
            cmap = {c.channel: c for c in channels}
            if set(cmap) != {'IN_APP','EMAIL','WEBHOOK','WHATSAPP'}:
                raise SystemExit(f'BLOCK7_CHANNEL_FAIL org={org.code}')
            if not cmap['IN_APP'].enabled or cmap['IN_APP'].configuration_status != 'READY':
                raise SystemExit(f'BLOCK7_CHANNEL_FAIL in_app org={org.code}')
        db.commit()
        sample = orgs[0]
        p = db.scalar(select(AlertPolicy).where(AlertPolicy.organization_id == sample.id, AlertPolicy.severity == 'ALTA'))
        print(f'BLOCK7_POLICY_OK org={sample.code} ALTA ack={p.acknowledge_sla_seconds}s resolve={p.resolve_sla_seconds}s max_level={p.max_escalation_level}')
        crows = list(db.scalars(select(NotificationChannel).where(NotificationChannel.organization_id == sample.id)))
        status = ','.join(f'{c.channel}={c.configuration_status}' for c in sorted(crows,key=lambda x:x.channel))
        print(f'BLOCK7_CHANNELS_OK {status}')

        event = db.scalar(select(SafetyDetectionEvent).where(SafetyDetectionEvent.operational_status != 'RESOLVED').order_by(SafetyDetectionEvent.confirmed_at.desc()))
        if event:
            now = datetime.now(timezone.utc)
            if not event.sla_ack_due_at or not event.sla_resolve_due_at:
                initialize_event_alert_state(db, event, now, create_notification=True)
            result = process_alerts(db, now, send_external=False)
            db.commit(); db.refresh(event)
            if not event.alert_priority or not event.sla_ack_due_at or not event.sla_resolve_due_at:
                raise SystemExit('BLOCK7_EVENT_RUNTIME_FAIL')
            print(f'BLOCK7_EVENT_RUNTIME_OK event={event.event_number} priority={event.alert_priority} ack={event.ack_sla_status} resolve={event.resolve_sla_status} level={event.escalation_level} processed={result.get("processed",0)}')
        else:
            print('BLOCK7_EVENT_RUNTIME_OK no_unresolved_events')

if __name__ == '__main__':
    main()
