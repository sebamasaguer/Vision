"""Bloque 9 dataset HYS, training pipeline, model registry y shadow deployment
Revision ID: 0011_block9
Revises: 0010_block8
"""
from alembic import op
import sqlalchemy as sa

revision='0011_block9'; down_revision='0010_block8'; branch_labels=None; depends_on=None


def upgrade():
    # Model registry fields on the existing version table.
    for name, typ, nullable in [
        ('artifact_uri', sa.String(500), True),
        ('artifact_sha256', sa.String(64), True),
        ('framework', sa.String(80), True),
        ('model_stage', sa.String(32), False),
        ('input_width', sa.Integer(), True),
        ('input_height', sa.Integer(), True),
        ('class_map', sa.JSON(), True),
        ('metrics_json', sa.JSON(), True),
        ('approved_at', sa.DateTime(timezone=True), True),
        ('approved_by_user_id', sa.Uuid(), True),
    ]:
        kw={'nullable':nullable}
        if name=='model_stage': kw['server_default']='REGISTERED'
        if name=='approved_by_user_id':
            op.add_column('vision_model_versions', sa.Column(name, typ, sa.ForeignKey('users.id', ondelete='SET NULL'), **kw))
        else:
            op.add_column('vision_model_versions', sa.Column(name, typ, **kw))
    op.create_index('ix_vision_model_versions_model_stage','vision_model_versions',['model_stage'])
    op.create_index('ix_vision_model_versions_artifact_sha256','vision_model_versions',['artifact_sha256'])

    op.create_table('ml_datasets',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('code',sa.String(80),nullable=False),
        sa.Column('name',sa.String(180),nullable=False),
        sa.Column('description',sa.Text(),nullable=True),
        sa.Column('license_name',sa.String(100),nullable=False,server_default='PROPRIETARY-HYS'),
        sa.Column('source_url',sa.String(500),nullable=True),
        sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.text('true')),
        sa.Column('created_by_user_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='SET NULL'),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('organization_id','code',name='uq_ml_dataset_org_code'),
    )
    for c in ['organization_id','code','active']:
        op.create_index(f'ix_ml_datasets_{c}','ml_datasets',[c])

    op.create_table('ml_dataset_versions',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('dataset_id',sa.Uuid(),sa.ForeignKey('ml_datasets.id',ondelete='CASCADE'),nullable=False),
        sa.Column('version',sa.String(50),nullable=False),
        sa.Column('status',sa.String(24),nullable=False,server_default='DRAFT'),
        sa.Column('classes',sa.JSON(),nullable=False),
        sa.Column('image_count',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('annotation_count',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('train_count',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('val_count',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('test_count',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('manifest_sha256',sa.String(64),nullable=True),
        sa.Column('storage_path',sa.String(500),nullable=True),
        sa.Column('notes',sa.Text(),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('frozen_at',sa.DateTime(timezone=True),nullable=True),
        sa.UniqueConstraint('dataset_id','version',name='uq_ml_dataset_version'),
    )
    op.create_index('ix_ml_dataset_versions_dataset_id','ml_dataset_versions',['dataset_id'])
    op.create_index('ix_ml_dataset_versions_status','ml_dataset_versions',['status'])

    op.create_table('ml_training_runs',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('dataset_version_id',sa.Uuid(),sa.ForeignKey('ml_dataset_versions.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('model_family',sa.String(80),nullable=False,server_default='YOLOX'),
        sa.Column('base_model',sa.String(80),nullable=False,server_default='yolox_nano'),
        sa.Column('status',sa.String(24),nullable=False,server_default='QUEUED'),
        sa.Column('epochs',sa.Integer(),nullable=False,server_default='30'),
        sa.Column('image_size',sa.Integer(),nullable=False,server_default='640'),
        sa.Column('batch_size',sa.Integer(),nullable=False,server_default='8'),
        sa.Column('device',sa.String(40),nullable=False,server_default='cpu'),
        sa.Column('command_line',sa.Text(),nullable=True),
        sa.Column('metrics',sa.JSON(),nullable=True),
        sa.Column('output_model_version_id',sa.Uuid(),sa.ForeignKey('vision_model_versions.id',ondelete='SET NULL'),nullable=True),
        sa.Column('error_message',sa.Text(),nullable=True),
        sa.Column('created_by_user_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='SET NULL'),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('started_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('completed_at',sa.DateTime(timezone=True),nullable=True),
    )
    for c in ['organization_id','dataset_version_id','status','output_model_version_id']:
        op.create_index(f'ix_ml_training_runs_{c}','ml_training_runs',[c])

    op.create_table('ml_model_deployments',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('camera_id',sa.Uuid(),sa.ForeignKey('cameras.id',ondelete='CASCADE'),nullable=True),
        sa.Column('model_version_id',sa.Uuid(),sa.ForeignKey('vision_model_versions.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('mode',sa.String(24),nullable=False),
        sa.Column('enabled',sa.Boolean(),nullable=False,server_default=sa.text('true')),
        sa.Column('started_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('ended_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('created_by_user_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='SET NULL'),nullable=True),
    )
    for c in ['organization_id','camera_id','model_version_id','mode','enabled']:
        op.create_index(f'ix_ml_model_deployments_{c}','ml_model_deployments',[c])

    op.create_table('ml_shadow_observations',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('camera_id',sa.Uuid(),sa.ForeignKey('cameras.id',ondelete='CASCADE'),nullable=False),
        sa.Column('deployment_id',sa.Uuid(),sa.ForeignKey('ml_model_deployments.id',ondelete='CASCADE'),nullable=False),
        sa.Column('track_id',sa.String(80),nullable=False),
        sa.Column('ppe_code',sa.String(80),nullable=False),
        sa.Column('baseline_status',sa.String(32),nullable=False),
        sa.Column('candidate_status',sa.String(32),nullable=False),
        sa.Column('baseline_confidence',sa.Float(),nullable=True),
        sa.Column('candidate_confidence',sa.Float(),nullable=True),
        sa.Column('agreement',sa.Boolean(),nullable=False,server_default=sa.text('false')),
        sa.Column('observed_at',sa.DateTime(timezone=True),nullable=False),
    )
    for c in ['organization_id','camera_id','deployment_id','track_id','ppe_code','agreement','observed_at']:
        op.create_index(f'ix_ml_shadow_observations_{c}','ml_shadow_observations',[c])


def downgrade():
    op.drop_table('ml_shadow_observations')
    op.drop_table('ml_model_deployments')
    op.drop_table('ml_training_runs')
    op.drop_table('ml_dataset_versions')
    op.drop_table('ml_datasets')
    op.drop_index('ix_vision_model_versions_artifact_sha256',table_name='vision_model_versions')
    op.drop_index('ix_vision_model_versions_model_stage',table_name='vision_model_versions')
    for c in ['approved_by_user_id','approved_at','metrics_json','class_map','input_height','input_width','model_stage','framework','artifact_sha256','artifact_uri']:
        op.drop_column('vision_model_versions',c)
