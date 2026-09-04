"""Bloque 0 foundation

Revision ID: 0001_block0
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_block0"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("organizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code", name="uq_organizations_code"),
    )
    op.create_table("roles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )
    op.create_table("permissions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )
    op.create_table("sites",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "code", name="uq_sites_org_code"),
    )
    op.create_index("ix_sites_org", "sites", ["organization_id"])
    op.create_table("plants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_id", sa.Uuid(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("site_id", "code", name="uq_plants_site_code"),
    )
    op.create_index("ix_plants_org", "plants", ["organization_id"])
    op.create_index("ix_plants_site", "plants", ["site_id"])
    op.create_table("sectors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_id", sa.Uuid(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plant_id", sa.Uuid(), sa.ForeignKey("plants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("plant_id", "code", name="uq_sectors_plant_code"),
    )
    op.create_index("ix_sectors_org", "sectors", ["organization_id"])
    op.create_index("ix_sectors_plant", "sectors", ["plant_id"])
    op.create_table("users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_org", "users", ["organization_id"])
    op.create_table("user_roles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Uuid(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table("role_permissions",
        sa.Column("role_id", sa.Uuid(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", sa.Uuid(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table("audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=True),
        sa.Column("before_value", sa.JSON(), nullable=True),
        sa.Column("after_value", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_org_created", "audit_logs", ["organization_id", "created_at"])
    op.create_table("system_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("key", sa.String(150), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "key", name="uq_system_settings_org_key"),
    )

def downgrade():
    op.drop_table("system_settings")
    op.drop_index("ix_audit_org_created", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_index("ix_users_org", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_sectors_plant", table_name="sectors")
    op.drop_index("ix_sectors_org", table_name="sectors")
    op.drop_table("sectors")
    op.drop_index("ix_plants_site", table_name="plants")
    op.drop_index("ix_plants_org", table_name="plants")
    op.drop_table("plants")
    op.drop_index("ix_sites_org", table_name="sites")
    op.drop_table("sites")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("organizations")
