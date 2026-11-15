"""Separate manager contact configuration by store; preserve legacy poster."""
from alembic import op
import sqlalchemy as sa

revision = "20261115_store_contact"
down_revision = "20260726_market_v1"
branch_labels = None
depends_on = None

def upgrade():
    if not sa.inspect(op.get_bind()).has_table("store_contact_settings"):
        op.create_table("store_contact_settings",
            sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), primary_key=True),
            sa.Column("poster_url", sa.String(500)),
            sa.Column("title", sa.String(50)),
            sa.Column("hint", sa.String(100)),
            sa.Column("updated_at", sa.DateTime(), nullable=False))

def downgrade():
    op.drop_table("store_contact_settings")
