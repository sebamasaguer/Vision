"""Bloque 10 dataset manager visual, ground truth y evaluación
Revision ID: 0012_block10
Revises: 0011_block9
"""
from alembic import op
import sqlalchemy as sa

revision='0012_block10'; down_revision='0011_block9'; branch_labels=None; depends_on=None


def upgrade():
    op.create_table('ml_dataset_frames',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('dataset_id',sa.Uuid(),sa.ForeignKey('ml_datasets.id',ondelete='CASCADE'),nullable=False),
        sa.Column('camera_id',sa.Uuid(),sa.ForeignKey('cameras.id',ondelete='SET NULL'),nullable=True),
        sa.Column('source_type',sa.String(24),nullable=False,server_default='UPLOAD'),
        sa.Column('source_ref',sa.String(500),nullable=True),
        sa.Column('frame_index',sa.Integer(),nullable=True),
        sa.Column('captured_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('image_path',sa.String(500),nullable=False),
        sa.Column('sha256',sa.String(64),nullable=False),
        sa.Column('width',sa.Integer(),nullable=False),
        sa.Column('height',sa.Integer(),nullable=False),
        sa.Column('curation_status',sa.String(24),nullable=False,server_default='PENDING'),
        sa.Column('ground_truth_status',sa.String(24),nullable=False,server_default='UNLABELED'),
        sa.Column('duplicate_of_id',sa.Uuid(),sa.ForeignKey('ml_dataset_frames.id',ondelete='SET NULL'),nullable=True),
        sa.Column('created_by_user_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='SET NULL'),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
    )
    for c in ['organization_id','dataset_id','camera_id','source_type','sha256','curation_status','ground_truth_status']:
        op.create_index(f'ix_ml_dataset_frames_{c}','ml_dataset_frames',[c])
    op.create_table('ml_ground_truth_annotations',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('frame_id',sa.Uuid(),sa.ForeignKey('ml_dataset_frames.id',ondelete='CASCADE'),nullable=False),
        sa.Column('class_code',sa.String(80),nullable=False),
        sa.Column('x',sa.Float(),nullable=False),sa.Column('y',sa.Float(),nullable=False),
        sa.Column('width',sa.Float(),nullable=False),sa.Column('height',sa.Float(),nullable=False),
        sa.Column('source',sa.String(24),nullable=False,server_default='MANUAL'),
        sa.Column('verified',sa.Boolean(),nullable=False,server_default=sa.text('false')),
        sa.Column('created_by_user_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='SET NULL'),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
    )
    for c in ['frame_id','class_code','verified']:
        op.create_index(f'ix_ml_ground_truth_annotations_{c}','ml_ground_truth_annotations',[c])
    op.create_table('ml_evaluation_runs',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('dataset_id',sa.Uuid(),sa.ForeignKey('ml_datasets.id',ondelete='CASCADE'),nullable=False),
        sa.Column('model_version_id',sa.Uuid(),sa.ForeignKey('vision_model_versions.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('camera_id',sa.Uuid(),sa.ForeignKey('cameras.id',ondelete='SET NULL'),nullable=True),
        sa.Column('status',sa.String(24),nullable=False,server_default='QUEUED'),
        sa.Column('iou_threshold',sa.Float(),nullable=False,server_default='0.5'),
        sa.Column('confidence_threshold',sa.Float(),nullable=False,server_default='0.35'),
        sa.Column('sample_count',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('metrics',sa.JSON(),nullable=True),
        sa.Column('error_message',sa.Text(),nullable=True),
        sa.Column('created_by_user_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='SET NULL'),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('started_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('completed_at',sa.DateTime(timezone=True),nullable=True),
    )
    for c in ['organization_id','dataset_id','model_version_id','camera_id','status']:
        op.create_index(f'ix_ml_evaluation_runs_{c}','ml_evaluation_runs',[c])


def downgrade():
    op.drop_table('ml_evaluation_runs')
    op.drop_table('ml_ground_truth_annotations')
    op.drop_table('ml_dataset_frames')
