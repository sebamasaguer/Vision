"""Bloque 6 gestion operativa, evidencias y revision humana inicial
Revision ID: 0008_block6
Revises: 0007_block5
"""
from alembic import op
import sqlalchemy as sa

revision='0008_block6'; down_revision='0007_block5'; branch_labels=None; depends_on=None


def upgrade():
    for name, typ, nullable, default in [
        ('operational_status', sa.String(24), False, 'NEW'),
        ('review_outcome', sa.String(24), False, 'PENDING'),
        ('assigned_to_user_id', sa.Uuid(), True, None),
        ('acknowledged_by_user_id', sa.Uuid(), True, None),
        ('acknowledged_at', sa.DateTime(timezone=True), True, None),
        ('reviewed_by_user_id', sa.Uuid(), True, None),
        ('reviewed_at', sa.DateTime(timezone=True), True, None),
        ('resolved_by_user_id', sa.Uuid(), True, None),
        ('resolved_at', sa.DateTime(timezone=True), True, None),
        ('review_notes', sa.Text(), True, None),
        ('resolution_note', sa.Text(), True, None),
        ('evidence_status', sa.String(24), False, 'PENDING'),
        ('evidence_count', sa.Integer(), False, '0'),
        ('evidence_captured_at', sa.DateTime(timezone=True), True, None),
        ('evidence_error', sa.String(500), True, None),
    ]:
        kwargs={'nullable': nullable}
        if default is not None: kwargs['server_default']=default
        if name.endswith('_user_id'):
            kwargs['nullable']=True
            col=sa.Column(name, typ, sa.ForeignKey('users.id',ondelete='SET NULL'), **kwargs)
        else:
            col=sa.Column(name, typ, **kwargs)
        op.add_column('safety_detection_events', col)
    for col in ['operational_status','review_outcome','assigned_to_user_id','acknowledged_at','resolved_at','evidence_status']:
        op.create_index(f'ix_safety_detection_events_{col}','safety_detection_events',[col])

    op.create_table('safety_event_evidence',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('event_id',sa.Uuid(),sa.ForeignKey('safety_detection_events.id',ondelete='CASCADE'),nullable=False),
        sa.Column('kind',sa.String(32),nullable=False),
        sa.Column('bucket',sa.String(120),nullable=False),
        sa.Column('object_key',sa.String(600),nullable=False,unique=True),
        sa.Column('mime_type',sa.String(120),nullable=False),
        sa.Column('sha256',sa.String(64),nullable=False),
        sa.Column('size_bytes',sa.BigInteger(),nullable=False),
        sa.Column('captured_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('source_frame_at',sa.String(80),nullable=True),
        sa.Column('immutable',sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column('metadata_json',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
    )
    for col in ['organization_id','event_id','kind','captured_at','sha256']:
        op.create_index(f'ix_safety_event_evidence_{col}','safety_event_evidence',[col])

    op.create_table('safety_event_notes',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('event_id',sa.Uuid(),sa.ForeignKey('safety_detection_events.id',ondelete='CASCADE'),nullable=False),
        sa.Column('author_user_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='SET NULL'),nullable=True),
        sa.Column('note_type',sa.String(24),nullable=False),
        sa.Column('body',sa.Text(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
    )
    for col in ['organization_id','event_id','author_user_id','created_at']:
        op.create_index(f'ix_safety_event_notes_{col}','safety_event_notes',[col])

    op.create_table('safety_event_actions',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('event_id',sa.Uuid(),sa.ForeignKey('safety_detection_events.id',ondelete='CASCADE'),nullable=False),
        sa.Column('actor_user_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='SET NULL'),nullable=True),
        sa.Column('action',sa.String(48),nullable=False),
        sa.Column('from_status',sa.String(24),nullable=True),
        sa.Column('to_status',sa.String(24),nullable=True),
        sa.Column('details',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
    )
    for col in ['organization_id','event_id','actor_user_id','action','created_at']:
        op.create_index(f'ix_safety_event_actions_{col}','safety_event_actions',[col])


def downgrade():
    op.drop_table('safety_event_actions')
    op.drop_table('safety_event_notes')
    op.drop_table('safety_event_evidence')
    for col in ['evidence_status','resolved_at','acknowledged_at','assigned_to_user_id','review_outcome','operational_status']:
        op.drop_index(f'ix_safety_detection_events_{col}',table_name='safety_detection_events')
    for c in ['evidence_error','evidence_captured_at','evidence_count','evidence_status','resolution_note','review_notes','resolved_at','resolved_by_user_id','reviewed_at','reviewed_by_user_id','acknowledged_at','acknowledged_by_user_id','assigned_to_user_id','review_outcome','operational_status']:
        op.drop_column('safety_detection_events',c)
