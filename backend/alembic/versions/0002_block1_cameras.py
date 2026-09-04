"""Bloque 1 cameras

Revision ID: 0002_block1
Revises: 0001_block0
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_block1"
down_revision = "0001_block0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cameras",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_id", sa.Uuid(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plant_id", sa.Uuid(), sa.ForeignKey("plants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sector_id", sa.Uuid(), sa.ForeignKey("sectors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("location", sa.String(250), nullable=True),
        sa.Column("source_type", sa.String(32), nullable=False, server_default="RTSP"),
        sa.Column("source_url_encrypted", sa.Text(), nullable=True),
        sa.Column("username_encrypted", sa.Text(), nullable=True),
        sa.Column("password_encrypted", sa.Text(), nullable=True),
        sa.Column("manufacturer", sa.String(120), nullable=True),
        sa.Column("model_name", sa.String(120), nullable=True),
        sa.Column("configured_width", sa.Integer(), nullable=True),
        sa.Column("configured_height", sa.Integer(), nullable=True),
        sa.Column("source_fps", sa.Float(), nullable=True),
        sa.Column("capture_fps", sa.Float(), nullable=False, server_default="5"),
        sa.Column("measured_fps", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="OFFLINE"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_connection_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_frame_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status_change_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "code", name="uq_cameras_org_code"),
    )
    for name, cols in [
        ("ix_cameras_org", ["organization_id"]), ("ix_cameras_site", ["site_id"]),
        ("ix_cameras_plant", ["plant_id"]), ("ix_cameras_sector", ["sector_id"]),
        ("ix_cameras_status", ["status"]), ("ix_cameras_last_frame", ["last_frame_at"]),
    ]:
        op.create_index(name, "cameras", cols)


def downgrade():
    op.drop_table("cameras")
