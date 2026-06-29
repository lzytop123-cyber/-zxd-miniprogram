"""轻量数据库结构升级（无需手工 SQL）。"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db.session import engine

logger = logging.getLogger(__name__)

MIGRATION_STATEMENTS = [
    "ALTER TABLE users ADD COLUMN invite_code VARCHAR(20)",
    "ALTER TABLE users ADD COLUMN invited_by INTEGER",
    "ALTER TABLE users ADD COLUMN study_goal VARCHAR(20)",
    "ALTER TABLE home_banners ADD COLUMN layout_type VARCHAR(20) DEFAULT 'text'",
    "ALTER TABLE home_banners ADD COLUMN image_url VARCHAR(500)",
    "ALTER TABLE home_banners ADD COLUMN link_path VARCHAR(200)",
    "ALTER TABLE home_carousel_settings ADD COLUMN hero_height INTEGER DEFAULT 520",
    "ALTER TABLE home_carousel_settings ADD COLUMN hero_mode VARCHAR(20) DEFAULT 'fullscreen'",
    "ALTER TABLE period_cards ADD COLUMN total_hours NUMERIC(5, 1)",
    "ALTER TABLE meituan_deal_mapping ADD COLUMN platform INTEGER DEFAULT 1",
    "ALTER TABLE reservations ADD COLUMN refund_remark VARCHAR(200)",
    "ALTER TABLE reservations ADD COLUMN refunded_at DATETIME",
    "ALTER TABLE reservations ADD COLUMN period_card_id INTEGER",
]

# 性能索引（存量库补建；已存在时忽略）
INDEX_STATEMENTS = [
    "CREATE INDEX ix_reservations_seat_time ON reservations (seat_id, start_time, end_time)",
    "CREATE INDEX ix_reservations_user ON reservations (user_id)",
    "CREATE INDEX ix_wallet_logs_user_created ON wallet_logs (user_id, created_at)",
]

_last_result: dict | None = None


def get_last_migration_result() -> dict:
    return _last_result or {"status": "unknown", "applied": [], "backfill_hours": 0}


def run_schema_migrations(db: Session) -> dict:
    global _last_result
    applied: list[str] = []
    errors: list[str] = []

    dialect = engine.dialect.name
    inspector = inspect(engine)
    period_columns = {c["name"] for c in inspector.get_columns("period_cards")} if inspector.has_table("period_cards") else set()

    with engine.begin() as conn:
        for stmt in MIGRATION_STATEMENTS:
            col_hint = stmt.split("ADD COLUMN")[-1].strip().split()[0] if "ADD COLUMN" in stmt else stmt[:40]
            if "period_cards" in stmt and "total_hours" in stmt and "total_hours" in period_columns:
                continue
            try:
                conn.execute(text(stmt))
                applied.append(col_hint)
            except Exception as exc:
                msg = str(exc).lower()
                if "duplicate" in msg or "already exists" in msg:
                    continue
                errors.append(f"{col_hint}: {exc.__class__.__name__}")

        backfill_hours = 0
        if inspector.has_table("period_cards"):
            try:
                result = conn.execute(
                    text(
                        "UPDATE period_cards SET total_hours = remaining_hours "
                        "WHERE card_type = 'hourly' AND total_hours IS NULL AND remaining_hours IS NOT NULL"
                    )
                )
                backfill_hours = result.rowcount or 0
            except Exception as exc:
                errors.append(f"backfill total_hours: {exc.__class__.__name__}")

    created_tables: list[str] = []
    try:
        from app.models import AdminOperationLog, RechargeOrder, StoreCalendarDay, SystemAnnouncement

        for model in (AdminOperationLog, SystemAnnouncement, StoreCalendarDay, RechargeOrder):
            model.__table__.create(bind=engine, checkfirst=True)
            if inspector.has_table(model.__tablename__):
                created_tables.append(model.__tablename__)
    except Exception as exc:
        errors.append(f"create tables: {exc.__class__.__name__}")

    # 团购券码唯一索引（防并发重复兑换）。已存在重复数据时会失败，记录后跳过。
    index_stmts = [
        "CREATE UNIQUE INDEX uq_meituan_orders_coupon_code ON meituan_orders (coupon_code)",
        *INDEX_STATEMENTS,
    ]
    for stmt in index_stmts:
        idx_name = stmt.split("INDEX")[1].strip().split()[0]
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
            applied.append(idx_name)
        except Exception as exc:
            msg = str(exc).lower()
            if not ("duplicate" in msg or "already exists" in msg or "exists" in msg):
                errors.append(f"{idx_name}: {exc.__class__.__name__}")

    _last_result = {
        "status": "ok" if not errors else "partial",
        "dialect": dialect,
        "applied": applied,
        "backfill_hours": backfill_hours,
        "created_tables": created_tables,
        "errors": errors,
    }
    if applied or backfill_hours:
        logger.info("schema migrate: applied=%s backfill_hours=%s", applied, backfill_hours)
    if errors:
        logger.warning("schema migrate errors: %s", errors)
    return _last_result
