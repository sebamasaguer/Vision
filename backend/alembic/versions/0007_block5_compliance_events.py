"""Bloque 5 motor de cumplimiento y safety events
Revision ID: 0007_block5
Revises: 0006_block4
"""
from alembic import op
import sqlalchemy as sa

revision='0007_block5'; down_revision='0006_block4'; branch_labels=None; depends_on=None


def upgrade():
    for name, typ, default in [
        ('compliance_enabled', sa.Boolean(), sa.false()),
        ('compliance_window_seconds', sa.Float(), '4.0'),
        ('compliance_min_persistence_seconds', sa.Float(), '2.0'),
        ('compliance_min_consensus_ratio', sa.Float(), '0.70'),
        ('compliance_min_missing_observations', sa.Integer(), '3'),
        ('compliance_cooldown_seconds', sa.Float(), '15.0'),
        ('compliance_clear_grace_seconds', sa.Float(), '1.0'),
        ('compliance_track_absence_close_seconds', sa.Float(), '3.0'),
    ]:
        op.add_column('camera_vision_settings', sa.Column(name, typ, nullable=False, server_default=default))
    op.create_index('ix_camera_vision_settings_compliance_enabled','camera_vision_settings',['compliance_enabled'])

    op.create_table('safety_detection_events',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('event_number',sa.String(48),nullable=False,unique=True),
        sa.Column('dedupe_key',sa.String(220),nullable=False),
        sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('site_id',sa.Uuid(),sa.ForeignKey('sites.id',ondelete='CASCADE'),nullable=False),
        sa.Column('plant_id',sa.Uuid(),sa.ForeignKey('plants.id',ondelete='CASCADE'),nullable=False),
        sa.Column('sector_id',sa.Uuid(),sa.ForeignKey('sectors.id',ondelete='CASCADE'),nullable=False),
        sa.Column('camera_id',sa.Uuid(),sa.ForeignKey('cameras.id',ondelete='CASCADE'),nullable=False),
        sa.Column('zone_id',sa.Uuid(),sa.ForeignKey('zones.id',ondelete='SET NULL'),nullable=True),
        sa.Column('ppe_type_id',sa.Uuid(),sa.ForeignKey('ppe_types.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('track_id',sa.String(64),nullable=False),
        sa.Column('ppe_code',sa.String(64),nullable=False),
        sa.Column('ppe_name',sa.String(160),nullable=False),
        sa.Column('requirement',sa.String(24),nullable=False),
        sa.Column('severity',sa.String(24),nullable=False),
        sa.Column('status',sa.String(24),nullable=False),
        sa.Column('detection_status',sa.String(24),nullable=False),
        sa.Column('first_observed_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('confirmed_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('last_seen_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('ended_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('duration_seconds',sa.Float(),nullable=False,server_default='0'),
        sa.Column('last_confidence',sa.Float(),nullable=True),
        sa.Column('min_confidence',sa.Float(),nullable=True),
        sa.Column('consensus_ratio',sa.Float(),nullable=False,server_default='0'),
        sa.Column('missing_observations',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('evaluable_observations',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('rule_snapshot',sa.JSON(),nullable=False),
        sa.Column('model_snapshot',sa.JSON(),nullable=False),
        sa.Column('close_reason',sa.String(80),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
    )
    for col in ['event_number','dedupe_key','organization_id','site_id','plant_id','sector_id','camera_id','zone_id','ppe_type_id','track_id','ppe_code','severity','status','last_seen_at']:
        op.create_index(f'ix_safety_detection_events_{col}','safety_detection_events',[col])
    op.create_index('ix_safety_event_dedupe_status','safety_detection_events',['dedupe_key','status'])

    op.create_table('compliance_evaluations',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('camera_id',sa.Uuid(),sa.ForeignKey('cameras.id',ondelete='CASCADE'),nullable=False),
        sa.Column('zone_id',sa.Uuid(),sa.ForeignKey('zones.id',ondelete='SET NULL'),nullable=True),
        sa.Column('ppe_type_id',sa.Uuid(),sa.ForeignKey('ppe_types.id',ondelete='SET NULL'),nullable=True),
        sa.Column('event_id',sa.Uuid(),sa.ForeignKey('safety_detection_events.id',ondelete='SET NULL'),nullable=True),
        sa.Column('track_id',sa.String(64),nullable=False),
        sa.Column('ppe_code',sa.String(64),nullable=False),
        sa.Column('observed_status',sa.String(24),nullable=False),
        sa.Column('compliance_status',sa.String(24),nullable=False),
        sa.Column('confidence',sa.Float(),nullable=True),
        sa.Column('consensus_ratio',sa.Float(),nullable=True),
        sa.Column('missing_observations',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('evaluable_observations',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('details',sa.JSON(),nullable=False),
        sa.Column('evaluated_at',sa.DateTime(timezone=True),nullable=False),
    )
    for col in ['organization_id','camera_id','zone_id','ppe_type_id','event_id','track_id','ppe_code','compliance_status','evaluated_at']:
        op.create_index(f'ix_compliance_evaluations_{col}','compliance_evaluations',[col])


def downgrade():
    op.drop_table('compliance_evaluations')
    op.drop_table('safety_detection_events')
    op.drop_index('ix_camera_vision_settings_compliance_enabled',table_name='camera_vision_settings')
    for c in ['compliance_track_absence_close_seconds','compliance_clear_grace_seconds','compliance_cooldown_seconds','compliance_min_missing_observations','compliance_min_consensus_ratio','compliance_min_persistence_seconds','compliance_window_seconds','compliance_enabled']:
        op.drop_column('camera_vision_settings',c)
