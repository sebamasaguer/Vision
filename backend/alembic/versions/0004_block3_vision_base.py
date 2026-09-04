"""Bloque 3 vision base
Revision ID: 0004_block3
Revises: 0003_block2
"""
from alembic import op
import sqlalchemy as sa
revision='0004_block3'; down_revision='0003_block2'; branch_labels=None; depends_on=None

def upgrade():
    op.create_table('vision_model_versions',
      sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('code',sa.String(80),nullable=False),sa.Column('name',sa.String(180),nullable=False),
      sa.Column('provider',sa.String(120),nullable=False),sa.Column('backend',sa.String(80),nullable=False),sa.Column('detector_type',sa.String(50),nullable=False),
      sa.Column('version',sa.String(80),nullable=False),sa.Column('license_name',sa.String(100),nullable=False),sa.Column('license_url',sa.String(500),nullable=True),
      sa.Column('commercial_use',sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.true()),
      sa.Column('is_default',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('notes',sa.Text(),nullable=True),sa.Column('model_metadata',sa.JSON(),nullable=True),
      sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('code',name='uq_vision_model_versions_code'))
    op.create_index('ix_vision_model_versions_code','vision_model_versions',['code']); op.create_index('ix_vision_model_versions_active','vision_model_versions',['active'])
    op.create_table('camera_vision_settings',
      sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
      sa.Column('camera_id',sa.Uuid(),sa.ForeignKey('cameras.id',ondelete='CASCADE'),nullable=False),sa.Column('model_version_id',sa.Uuid(),sa.ForeignKey('vision_model_versions.id',ondelete='RESTRICT'),nullable=False),
      sa.Column('enabled',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('inference_fps',sa.Float(),nullable=False,server_default='1'),
      sa.Column('min_confidence',sa.Float(),nullable=False,server_default='0.55'),sa.Column('nms_iou_threshold',sa.Float(),nullable=False,server_default='0.45'),
      sa.Column('tracker_iou_threshold',sa.Float(),nullable=False,server_default='0.20'),sa.Column('tracker_max_missed_frames',sa.Integer(),nullable=False,server_default='4'),
      sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
      sa.UniqueConstraint('camera_id',name='uq_camera_vision_setting_camera'))
    for n,c in [('ix_camera_vision_settings_org',['organization_id']),('ix_camera_vision_settings_camera',['camera_id']),('ix_camera_vision_settings_model',['model_version_id']),('ix_camera_vision_settings_enabled',['enabled'])]: op.create_index(n,'camera_vision_settings',c)

def downgrade():
    op.drop_table('camera_vision_settings'); op.drop_table('vision_model_versions')
