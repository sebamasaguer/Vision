"""Bloque 8 analytics ejecutivo, limpieza controlada y archivado QA
Revision ID: 0010_block8
Revises: 0009_block7
"""
from alembic import op
import sqlalchemy as sa

revision='0010_block8'; down_revision='0009_block7'; branch_labels=None; depends_on=None

def upgrade():
    for name, typ, nullable, default in [
        ('data_origin', sa.String(24), False, 'OPERATIONAL'),
        ('analytics_excluded', sa.Boolean(), False, 'false'),
        ('archived_at', sa.DateTime(timezone=True), True, None),
        ('archived_by_user_id', sa.Uuid(), True, None),
        ('archive_reason', sa.String(240), True, None),
    ]:
        kw={'nullable':nullable}
        if default is not None: kw['server_default']=sa.text(default) if default in ('false','true') else default
        fk = sa.ForeignKey('users.id',ondelete='SET NULL') if name=='archived_by_user_id' else None
        col=sa.Column(name,typ,fk,**kw) if fk else sa.Column(name,typ,**kw)
        op.add_column('safety_detection_events', col)
    for col in ['data_origin','analytics_excluded','archived_at']:
        op.create_index(f'ix_safety_detection_events_{col}','safety_detection_events',[col])
    op.create_table('pilot_cleanup_runs',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('actor_user_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='SET NULL'),nullable=True),
        sa.Column('status',sa.String(24),nullable=False),
        sa.Column('reason',sa.String(500),nullable=False),
        sa.Column('archived_events',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('closed_technical_events',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('resolved_operational_events',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('disabled_compliance_cameras',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('restored_sla_policies',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('preserved_evidence',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('preserved_actions',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('snapshot_json',sa.JSON(),nullable=False),
        sa.Column('started_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('completed_at',sa.DateTime(timezone=True),nullable=True),
    )
    for col in ['organization_id','status','started_at']:
        op.create_index(f'ix_pilot_cleanup_runs_{col}','pilot_cleanup_runs',[col])

def downgrade():
    op.drop_table('pilot_cleanup_runs')
    for col in ['archived_at','analytics_excluded','data_origin']:
        op.drop_index(f'ix_safety_detection_events_{col}',table_name='safety_detection_events')
    for c in ['archive_reason','archived_by_user_id','archived_at','analytics_excluded','data_origin']:
        op.drop_column('safety_detection_events',c)
