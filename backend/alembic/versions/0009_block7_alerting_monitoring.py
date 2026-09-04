"""Bloque 7 alertas operativas, SLA, escalamiento y notificaciones
Revision ID: 0009_block7
Revises: 0008_block6
"""
from alembic import op
import sqlalchemy as sa

revision='0009_block7'; down_revision='0008_block6'; branch_labels=None; depends_on=None


def upgrade():
    for name, typ, nullable, default in [
        ('alert_priority', sa.String(24), False, 'NORMAL'),
        ('sla_ack_due_at', sa.DateTime(timezone=True), True, None),
        ('sla_resolve_due_at', sa.DateTime(timezone=True), True, None),
        ('ack_sla_status', sa.String(24), False, 'PENDING'),
        ('resolve_sla_status', sa.String(24), False, 'PENDING'),
        ('escalation_level', sa.Integer(), False, '0'),
        ('next_escalation_at', sa.DateTime(timezone=True), True, None),
        ('last_escalated_at', sa.DateTime(timezone=True), True, None),
        ('last_notification_at', sa.DateTime(timezone=True), True, None),
    ]:
        kwargs={'nullable':nullable}
        if default is not None: kwargs['server_default']=default
        op.add_column('safety_detection_events', sa.Column(name,typ,**kwargs))
    for col in ['alert_priority','sla_ack_due_at','sla_resolve_due_at','ack_sla_status','resolve_sla_status','escalation_level','next_escalation_at']:
        op.create_index(f'ix_safety_detection_events_{col}','safety_detection_events',[col])

    op.create_table('alert_policies',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('severity',sa.String(24),nullable=False),
        sa.Column('name',sa.String(160),nullable=False),
        sa.Column('acknowledge_sla_seconds',sa.Integer(),nullable=False),
        sa.Column('resolve_sla_seconds',sa.Integer(),nullable=False),
        sa.Column('escalation_after_seconds',sa.Integer(),nullable=False),
        sa.Column('escalation_repeat_seconds',sa.Integer(),nullable=False),
        sa.Column('max_escalation_level',sa.Integer(),nullable=False),
        sa.Column('notification_channels',sa.JSON(),nullable=False),
        sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('organization_id','severity',name='uq_alert_policy_org_severity'),
    )
    for col in ['organization_id','severity','active']:
        op.create_index(f'ix_alert_policies_{col}','alert_policies',[col])

    op.create_table('notification_channels',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('channel',sa.String(32),nullable=False),
        sa.Column('enabled',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('configuration_status',sa.String(32),nullable=False,server_default='CONFIG_REQUIRED'),
        sa.Column('destination',sa.String(1000),nullable=True),
        sa.Column('config_json',sa.JSON(),nullable=False),
        sa.Column('last_test_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('last_test_status',sa.String(32),nullable=True),
        sa.Column('last_error',sa.String(1000),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('organization_id','channel',name='uq_notification_channel_org_type'),
    )
    for col in ['organization_id','channel','enabled','configuration_status']:
        op.create_index(f'ix_notification_channels_{col}','notification_channels',[col])

    op.create_table('alert_escalations',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('event_id',sa.Uuid(),sa.ForeignKey('safety_detection_events.id',ondelete='CASCADE'),nullable=False),
        sa.Column('level',sa.Integer(),nullable=False),
        sa.Column('reason',sa.String(64),nullable=False),
        sa.Column('status',sa.String(24),nullable=False),
        sa.Column('scheduled_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('executed_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('details',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('event_id','level',name='uq_alert_escalation_event_level'),
    )
    for col in ['organization_id','event_id','level','status','executed_at']:
        op.create_index(f'ix_alert_escalations_{col}','alert_escalations',[col])

    op.create_table('notification_deliveries',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('event_id',sa.Uuid(),sa.ForeignKey('safety_detection_events.id',ondelete='CASCADE'),nullable=False),
        sa.Column('channel_id',sa.Uuid(),sa.ForeignKey('notification_channels.id',ondelete='SET NULL'),nullable=True),
        sa.Column('channel',sa.String(32),nullable=False),
        sa.Column('trigger_type',sa.String(64),nullable=False),
        sa.Column('escalation_level',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('recipient',sa.String(1000),nullable=True),
        sa.Column('status',sa.String(32),nullable=False),
        sa.Column('attempt_count',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('payload_snapshot',sa.JSON(),nullable=False),
        sa.Column('external_reference',sa.String(300),nullable=True),
        sa.Column('error_message',sa.String(1000),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('sent_at',sa.DateTime(timezone=True),nullable=True),
        sa.UniqueConstraint('event_id','channel','trigger_type','escalation_level',name='uq_notification_delivery_dedupe'),
    )
    for col in ['organization_id','event_id','channel','status','trigger_type','created_at','sent_at']:
        op.create_index(f'ix_notification_deliveries_{col}','notification_deliveries',[col])


def downgrade():
    op.drop_table('notification_deliveries')
    op.drop_table('alert_escalations')
    op.drop_table('notification_channels')
    op.drop_table('alert_policies')
    for col in ['next_escalation_at','escalation_level','resolve_sla_status','ack_sla_status','sla_resolve_due_at','sla_ack_due_at','alert_priority']:
        op.drop_index(f'ix_safety_detection_events_{col}',table_name='safety_detection_events')
    for c in ['last_notification_at','last_escalated_at','next_escalation_at','escalation_level','resolve_sla_status','ack_sla_status','sla_resolve_due_at','sla_ack_due_at','alert_priority']:
        op.drop_column('safety_detection_events',c)
