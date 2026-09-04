"""Bloque 2 zones, PPE catalog and rules

Revision ID: 0003_block2
Revises: 0002_block1
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_block2"
down_revision = "0002_block1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ppe_types",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.String(600), nullable=True),
        sa.Column("icon", sa.String(80), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criticality", sa.String(24), nullable=False, server_default="ADVERTENCIA"),
        sa.Column("color", sa.String(16), nullable=False, server_default="#4fe2b6"),
        sa.Column("detector_class", sa.String(120), nullable=True),
        sa.Column("min_confidence", sa.Float(), nullable=False, server_default="0.70"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ppe_types_code", "ppe_types", ["code"])
    op.create_index("ix_ppe_types_active", "ppe_types", ["active"])

    op.create_table(
        "zones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_id", sa.Uuid(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plant_id", sa.Uuid(), sa.ForeignKey("plants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sector_id", sa.Uuid(), sa.ForeignKey("sectors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("camera_id", sa.Uuid(), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.String(600), nullable=True),
        sa.Column("polygon_points", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("camera_id", "code", name="uq_zones_camera_code"),
    )
    for name, cols in [
        ("ix_zones_org", ["organization_id"]), ("ix_zones_site", ["site_id"]),
        ("ix_zones_plant", ["plant_id"]), ("ix_zones_sector", ["sector_id"]),
        ("ix_zones_camera", ["camera_id"]), ("ix_zones_active", ["active"]),
    ]:
        op.create_index(name, "zones", cols)

    op.create_table(
        "zone_ppe_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("zone_id", sa.Uuid(), sa.ForeignKey("zones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ppe_type_id", sa.Uuid(), sa.ForeignKey("ppe_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requirement", sa.String(24), nullable=False, server_default="REQUIRED"),
        sa.Column("severity", sa.String(24), nullable=False, server_default="ADVERTENCIA"),
        sa.Column("min_confidence", sa.Float(), nullable=True),
        sa.Column("schedule_start", sa.String(5), nullable=True),
        sa.Column("schedule_end", sa.String(5), nullable=True),
        sa.Column("task", sa.String(180), nullable=True),
        sa.Column("risk_level", sa.String(80), nullable=True),
        sa.Column("operation_type", sa.String(120), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("zone_id", "ppe_type_id", name="uq_zone_ppe_rule"),
    )
    op.create_index("ix_zone_ppe_rules_org", "zone_ppe_rules", ["organization_id"])
    op.create_index("ix_zone_ppe_rules_zone", "zone_ppe_rules", ["zone_id"])
    op.create_index("ix_zone_ppe_rules_ppe", "zone_ppe_rules", ["ppe_type_id"])
    op.create_index("ix_zone_ppe_rules_active", "zone_ppe_rules", ["active"])


def downgrade():
    op.drop_table("zone_ppe_rules")
    op.drop_table("zones")
    op.drop_table("ppe_types")
