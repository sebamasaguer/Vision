"""Bloque 4 PPE real baseline
Revision ID: 0006_block4
Revises: 0005_hotfix041
"""
from alembic import op
import sqlalchemy as sa
revision='0006_block4'; down_revision='0005_hotfix041'; branch_labels=None; depends_on=None

def upgrade():
    op.add_column('camera_vision_settings',sa.Column('ppe_enabled',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('camera_vision_settings',sa.Column('ppe_model_version_id',sa.Uuid(),nullable=True))
    op.add_column('camera_vision_settings',sa.Column('ppe_min_visibility_ratio',sa.Float(),nullable=False,server_default='0.70'))
    op.add_column('camera_vision_settings',sa.Column('ppe_uncertainty_margin',sa.Float(),nullable=False,server_default='0.05'))
    op.create_foreign_key('fk_camera_vision_ppe_model','camera_vision_settings','vision_model_versions',['ppe_model_version_id'],['id'],ondelete='RESTRICT')
    op.create_index('ix_camera_vision_settings_ppe_model','camera_vision_settings',['ppe_model_version_id'])

def downgrade():
    op.drop_index('ix_camera_vision_settings_ppe_model',table_name='camera_vision_settings')
    op.drop_constraint('fk_camera_vision_ppe_model','camera_vision_settings',type_='foreignkey')
    for c in ['ppe_uncertainty_margin','ppe_min_visibility_ratio','ppe_model_version_id','ppe_enabled']:
        op.drop_column('camera_vision_settings',c)
