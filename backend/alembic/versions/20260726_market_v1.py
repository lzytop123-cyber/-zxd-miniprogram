"""上岸集市 v1：学员闲置资料信息发布（可回退）。

Upgrade: 创建集市表并为 users 增加集市字段。
Downgrade: 删除集市表并移除 users 集市字段。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260726_market_v1"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    user_cols = {c["name"] for c in inspector.get_columns("users")} if inspector.has_table("users") else set()

    def add_user_col(name: str, col: sa.Column) -> None:
        if name not in user_cols:
            op.add_column("users", col)

    add_user_col("market_banned", sa.Column("market_banned", sa.Integer(), server_default="0"))
    add_user_col("market_ban_reason", sa.Column("market_ban_reason", sa.String(200), nullable=True))
    add_user_col("market_ban_until", sa.Column("market_ban_until", sa.DateTime(), nullable=True))
    add_user_col(
        "market_violation_count",
        sa.Column("market_violation_count", sa.Integer(), server_default="0"),
    )
    add_user_col("market_wechat_id", sa.Column("market_wechat_id", sa.String(64), nullable=True))
    add_user_col("preferred_store_id", sa.Column("preferred_store_id", sa.Integer(), nullable=True))

    if not inspector.has_table("market_categories"):
        op.create_table(
            "market_categories",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("type", sa.String(20), nullable=False),
            sa.Column("code", sa.String(40), nullable=False),
            sa.Column("name", sa.String(50), nullable=False),
            sa.Column("sort_order", sa.Integer(), server_default="0"),
            sa.Column("status", sa.Integer(), server_default="1"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("type", "code", name="uq_market_category_type_code"),
        )

    if not inspector.has_table("market_listings"):
        op.create_table(
            "market_listings",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
            sa.Column("exam_category_id", sa.Integer(), sa.ForeignKey("market_categories.id"), nullable=False),
            sa.Column("material_category_id", sa.Integer(), sa.ForeignKey("market_categories.id"), nullable=False),
            sa.Column("title", sa.String(100), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("price", sa.Numeric(10, 2), server_default="0"),
            sa.Column("is_free", sa.Integer(), server_default="0"),
            sa.Column("images", sa.JSON()),
            sa.Column("copyright_declared", sa.Integer(), server_default="0"),
            sa.Column("copyright_text_version", sa.String(20)),
            sa.Column("status", sa.String(20), server_default="draft"),
            sa.Column("reject_reason", sa.String(200)),
            sa.Column("view_count", sa.Integer(), server_default="0"),
            sa.Column("favorite_count", sa.Integer(), server_default="0"),
            sa.Column("contact_count", sa.Integer(), server_default="0"),
            sa.Column("published_at", sa.DateTime()),
            sa.Column("reviewed_at", sa.DateTime()),
            sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("admin_users.id")),
            sa.Column("content_safe_text_ok", sa.Integer()),
            sa.Column("content_safe_image_ok", sa.Integer()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("ix_market_listings_status_published", "market_listings", ["status", "published_at"])
        op.create_index("ix_market_listings_store_status", "market_listings", ["store_id", "status"])
        op.create_index("ix_market_listings_user", "market_listings", ["user_id"])

    if not inspector.has_table("market_favorites"):
        op.create_table(
            "market_favorites",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("listing_id", sa.Integer(), sa.ForeignKey("market_listings.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "listing_id", name="uq_market_favorite"),
        )

    if not inspector.has_table("market_contact_requests"):
        op.create_table(
            "market_contact_requests",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("listing_id", sa.Integer(), sa.ForeignKey("market_listings.id"), nullable=False),
            sa.Column("buyer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("seller_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("message", sa.String(200)),
            sa.Column("status", sa.String(20), server_default="pending"),
            sa.Column("reveal_type", sa.String(20)),
            sa.Column("reveal_value", sa.String(100)),
            sa.Column("decided_at", sa.DateTime()),
            sa.Column("expired_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )

    if not inspector.has_table("market_reports"):
        op.create_table(
            "market_reports",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("listing_id", sa.Integer(), sa.ForeignKey("market_listings.id"), nullable=False),
            sa.Column("reporter_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("reason_code", sa.String(40), nullable=False),
            sa.Column("detail", sa.String(500)),
            sa.Column("images", sa.JSON()),
            sa.Column("status", sa.String(20), server_default="pending"),
            sa.Column("handler_admin_id", sa.Integer(), sa.ForeignKey("admin_users.id")),
            sa.Column("handle_note", sa.String(200)),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("handled_at", sa.DateTime()),
        )

    if not inspector.has_table("market_sensitive_words"):
        op.create_table(
            "market_sensitive_words",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("word", sa.String(50), nullable=False, unique=True),
            sa.Column("level", sa.String(20), server_default="block"),
            sa.Column("status", sa.Integer(), server_default="1"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )

    if not inspector.has_table("market_moderation_logs"):
        op.create_table(
            "market_moderation_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("target_type", sa.String(30), nullable=False),
            sa.Column("target_id", sa.String(50), nullable=False),
            sa.Column("action", sa.String(50), nullable=False),
            sa.Column("admin_id", sa.Integer(), sa.ForeignKey("admin_users.id")),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("detail", sa.Text()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )


def downgrade() -> None:
    for table in (
        "market_moderation_logs",
        "market_sensitive_words",
        "market_reports",
        "market_contact_requests",
        "market_favorites",
        "market_listings",
        "market_categories",
    ):
        op.drop_table(table)

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    user_cols = {c["name"] for c in inspector.get_columns("users")} if inspector.has_table("users") else set()
    for col in (
        "preferred_store_id",
        "market_wechat_id",
        "market_violation_count",
        "market_ban_until",
        "market_ban_reason",
        "market_banned",
    ):
        if col in user_cols:
            op.drop_column("users", col)
