"""Hotfix v0.4.1 person detector hardening

Revision ID: 0005_hotfix041
Revises: 0004_block3
"""
from alembic import op
import sqlalchemy as sa

revision = '0005_hotfix041'
down_revision = '0004_block3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('camera_vision_settings', sa.Column('tracker_min_hits_to_confirm', sa.Integer(), nullable=False, server_default='3'))
    op.add_column('camera_vision_settings', sa.Column('min_box_area_ratio', sa.Float(), nullable=False, server_default='0.015'))
    op.add_column('camera_vision_settings', sa.Column('max_box_area_ratio', sa.Float(), nullable=False, server_default='0.18'))
    op.add_column('camera_vision_settings', sa.Column('min_height_ratio', sa.Float(), nullable=False, server_default='0.18'))
    op.add_column('camera_vision_settings', sa.Column('min_aspect_ratio', sa.Float(), nullable=False, server_default='0.28'))
    op.add_column('camera_vision_settings', sa.Column('max_aspect_ratio', sa.Float(), nullable=False, server_default='0.95'))
    op.add_column('camera_vision_settings', sa.Column('top_band_reject_y_ratio', sa.Float(), nullable=False, server_default='0.15'))
    op.add_column('camera_vision_settings', sa.Column('top_band_reject_bottom_ratio', sa.Float(), nullable=False, server_default='0.62'))

    # Endurece valores existentes de v0.4.0 sin sobrescribir configuraciones explícitas
    # salvo los defaults originales del Bloque 3.
    op.execute("""
        UPDATE camera_vision_settings
        SET min_confidence = CASE WHEN min_confidence = 0.55 THEN 0.62 ELSE min_confidence END,
            nms_iou_threshold = CASE WHEN nms_iou_threshold = 0.45 THEN 0.35 ELSE nms_iou_threshold END,
            tracker_iou_threshold = CASE WHEN tracker_iou_threshold = 0.20 THEN 0.25 ELSE tracker_iou_threshold END
    """)


def downgrade():
    for column in [
        'top_band_reject_bottom_ratio', 'top_band_reject_y_ratio',
        'max_aspect_ratio', 'min_aspect_ratio', 'min_height_ratio',
        'max_box_area_ratio', 'min_box_area_ratio', 'tracker_min_hits_to_confirm'
    ]:
        op.drop_column('camera_vision_settings', column)
