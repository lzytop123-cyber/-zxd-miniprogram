"""Database seed script for development."""

from datetime import date, time, timedelta
from decimal import Decimal

from sqlalchemy import select, text

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models import (
    AdminUser,
    BillType,
    BleLock,
    Coupon,
    MeituanDealMapping,
    PricingRule,
    RewardType,
    Seat,
    Store,
    User,
    Zone,
)

# 每区 8 座，共 24 个可选座位（4 列 × 2 行）
SEAT_ZONE_SPECS = (
    ("A区", "A", "standard", 0, 40),
    ("B区", "B", "window", 1, 180),
    ("C区", "C", "standard", 2, 320),
)
SEATS_PER_ZONE = 8


# 云老板验券返回的 dealId → 期限卡权益（美团后台 ID 可能不同，以验券返回为准）
REAL_DEAL_MAPPINGS = (
    # 云老板实测返回的 dealId
    ("1457226281", "团购测试四小时", RewardType.hours, 4, None, None),
    # 美团开店宝团购列表 ID（验券若返回这些 ID 可直接匹配）
    ("1538184020", "团购测试四小时", RewardType.hours, 4, None, None),
    ("1380905696", "「全区域通用 固定座位」季卡", RewardType.quarter_pass, 90, None, None),
    ("1372550283", "「全区域通用 任意30次」30次卡", RewardType.session, 30, None, None),
    ("1378191332", "「全区域通用 可自选」四小时卡", RewardType.hours, 4, None, None),
    ("1358350526", "「全区域通用」十次卡", RewardType.session, 10, None, None),
    ("1345243007", "「可分次·十次通用库」50小时", RewardType.hours, 50, None, None),
    ("1344290952", "「上班族」月卡", RewardType.month_pass, 30, None, None),
    ("1344305321", "「新客专享·全区域通用」月卡", RewardType.month_pass, 30, None, None),
    ("1344307152", "「全区域通用 固定座位」月卡", RewardType.month_pass, 30, None, None),
    ("1344310042", "「全区域通用」周卡", RewardType.week_pass, 7, None, None),
    ("1344305196", "「全区域通坐 可复购」日卡", RewardType.day_pass, 1, None, None),
    ("1344196515", "「新客专享 全区域通坐」三天卡", RewardType.day_pass, 3, None, None),
    ("1344167767", "「新客专享 全区域通坐」日卡", RewardType.day_pass, 1, None, None),
    ("1392559935", "「新客专享·全区域通坐」日卡", RewardType.day_pass, 1, None, None),
    ("1344166440", "「新客专享 全区域通坐」四小时", RewardType.hours, 4, None, None),
)


def _ensure_real_deal_mappings(db, store: Store) -> int:
    added = 0
    for deal_id, name, reward_type, value, ns, ne in REAL_DEAL_MAPPINGS:
        row = db.scalar(select(MeituanDealMapping).where(MeituanDealMapping.deal_id == deal_id))
        if row:
            row.deal_name = name
            row.reward_type = reward_type
            row.reward_value = value
            row.night_start = ns
            row.night_end = ne
            row.is_active = 1
            continue
        db.add(
            MeituanDealMapping(
                store_id=store.id,
                deal_id=deal_id,
                deal_name=name,
                reward_type=reward_type,
                reward_value=value,
                night_start=ns,
                night_end=ne,
                is_active=1,
            )
        )
        added += 1
    return added


def _seat_position(index: int, start_y: int) -> tuple[int, int]:
    col = (index - 1) % 4
    row = (index - 1) // 4
    return 30 + col * 90, start_y + row * 70


def _ensure_store_seats(db, store: Store) -> int:
    """补全门店座位（已有则跳过，支持重复执行 seed）。"""
    zones: dict[str, Zone] = {}
    for name, prefix, zone_type, sort_order, _ in SEAT_ZONE_SPECS:
        zone = db.scalar(select(Zone).where(Zone.store_id == store.id, Zone.name == name))
        if not zone:
            zone = Zone(store_id=store.id, name=name, type=zone_type, sort_order=sort_order)
            db.add(zone)
            db.flush()
        zones[prefix] = zone

    existing_codes = {
        s.seat_code
        for s in db.scalars(select(Seat).where(Seat.store_id == store.id, Seat.is_buffer == 0)).all()
    }
    added = []
    for name, prefix, zone_type, _, start_y in SEAT_ZONE_SPECS:
        for i in range(1, SEATS_PER_ZONE + 1):
            code = f"{prefix}{i:02d}"
            if code in existing_codes:
                continue
            pos_x, pos_y = _seat_position(i, start_y)
            added.append(
                Seat(
                    store_id=store.id,
                    zone_id=zones[prefix].id,
                    seat_code=code,
                    seat_type=zone_type,
                    has_outlet=1,
                    has_curtain=1 if prefix == "C" else 0,
                    pos_x=pos_x,
                    pos_y=pos_y,
                )
            )
    if added:
        db.add_all(added)

    # 统一刷新已有座位的分布图坐标
    for name, prefix, zone_type, _, start_y in SEAT_ZONE_SPECS:
        for i in range(1, SEATS_PER_ZONE + 1):
            code = f"{prefix}{i:02d}"
            seat = db.scalar(
                select(Seat).where(Seat.store_id == store.id, Seat.seat_code == code)
            )
            if not seat:
                continue
            pos_x, pos_y = _seat_position(i, start_y)
            seat.pos_x = pos_x
            seat.pos_y = pos_y
            seat.zone_id = zones[prefix].id
            seat.seat_type = zone_type

    return len(added)


def _ensure_quarterly_pricing(db, store: Store) -> bool:
    row = db.scalar(
        select(PricingRule).where(
            PricingRule.store_id == store.id,
            PricingRule.bill_type == BillType.quarterly,
        )
    )
    if row:
        return False
    db.add(
        PricingRule(
            store_id=store.id,
            bill_type=BillType.quarterly,
            seat_type="standard",
            price=Decimal("1307.00"),
            valid_days=90,
            remark="90天不限时",
            sort_order=3,
            is_active=1,
        )
    )
    return True


def _ensure_session_pricing(db, store: Store) -> bool:
    row = db.scalar(
        select(PricingRule).where(
            PricingRule.store_id == store.id,
            PricingRule.bill_type == BillType.session,
        )
    )
    if row:
        row.price = Decimal("58.00")
        row.remark = "按自然日计费，每天扣1次"
        row.min_hours = None
        row.max_hours = None
        return False
    db.add(
        PricingRule(
            store_id=store.id,
            bill_type=BillType.session,
            seat_type="standard",
            price=Decimal("58.00"),
            remark="按自然日计费，每天扣1次",
            sort_order=2,
            is_active=1,
        )
    )
    return True


def _ensure_weekly_pricing(db, store: Store) -> bool:
    if db.scalar(
        select(PricingRule).where(
            PricingRule.store_id == store.id,
            PricingRule.bill_type == BillType.weekly,
        )
    ):
        return False
    db.add(
        PricingRule(
            store_id=store.id,
            bill_type=BillType.weekly,
            seat_type="standard",
            price=Decimal("122.00"),
            valid_days=7,
            remark="7天不限时",
            sort_order=2,
            is_active=1,
        )
    )
    return True


def seed():
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()
    db = SessionLocal()
    try:
        if not db.scalar(select(Store).limit(1)):
            store = Store(
                name="知行岛平阳路店",
                address="太原市平阳路睿鼎国际中心A座25层",
                latitude=Decimal("37.8706"),
                longitude=Decimal("112.5489"),
                open_time=time(0, 0),
                close_time=time(0, 0),
                cover_images=["https://via.placeholder.com/800x400?text=ZXD"],
                floor_plan="https://via.placeholder.com/600x400?text=FloorPlan",
                wifi_name="ZXD-WiFi",
                wifi_password="zxd123456",
                status=1,
            )
            db.add(store)
            db.flush()

            zone_a = Zone(store_id=store.id, name="A区", type="standard", sort_order=0)
            zone_b = Zone(store_id=store.id, name="B区", type="window", sort_order=1)
            db.add_all([zone_a, zone_b])
            db.flush()

            _ensure_store_seats(db, store)

            pricing = [
                PricingRule(
                    store_id=store.id,
                    bill_type=BillType.hourly,
                    seat_type="standard",
                    price=Decimal("15.00"),
                    min_hours=2,
                    max_hours=24,
                    remark="按小时计费",
                    sort_order=0,
                ),
                PricingRule(
                    store_id=store.id,
                    bill_type=BillType.daily,
                    seat_type="standard",
                    price=Decimal("58.00"),
                    valid_days=1,
                    remark="全天不限时",
                    sort_order=1,
                ),
                PricingRule(
                    store_id=store.id,
                    bill_type=BillType.weekly,
                    seat_type="standard",
                    price=Decimal("122.00"),
                    valid_days=7,
                    remark="7天不限时",
                    sort_order=2,
                ),
                PricingRule(
                    store_id=store.id,
                    bill_type=BillType.monthly,
                    seat_type="standard",
                    price=Decimal("368.00"),
                    valid_days=30,
                    remark="30天不限时",
                    sort_order=3,
                ),
                PricingRule(
                    store_id=store.id,
                    bill_type=BillType.night,
                    seat_type="standard",
                    price=Decimal("39.00"),
                    night_start=time(18, 0),
                    night_end=time(0, 0),
                    remark="单次夜读票",
                    sort_order=4,
                ),
                PricingRule(
                    store_id=store.id,
                    bill_type=BillType.night_monthly,
                    seat_type="standard",
                    price=Decimal("198.00"),
                    night_start=time(18, 0),
                    night_end=time(23, 59, 59),
                    valid_days=30,
                    remark="晚自习月卡",
                    sort_order=5,
                ),
            ]
            db.add_all(pricing)

            db.add(
                BleLock(
                    store_id=store.id,
                    lock_name="前门",
                    lock_id="mock_lock_001",
                    mac_address="AA:BB:CC:DD:EE:FF",
                    lock_data="mock_lock_data_front_door",
                    battery_level=95,
                )
            )

        if not db.scalar(select(AdminUser).limit(1)):
            db.add(
                AdminUser(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                    name="系统管理员",
                )
            )

        store = db.scalar(select(Store).limit(1))
        if store:
            added = _ensure_store_seats(db, store)
            if added:
                print(f"Added {added} seats.")
            mapped = _ensure_real_deal_mappings(db, store)
            if mapped:
                print(f"Added {mapped} real deal mapping(s).")
            if _ensure_weekly_pricing(db, store):
                print("Added weekly pricing rule.")
            if _ensure_session_pricing(db, store):
                print("Added session pricing rule.")
            if _ensure_quarterly_pricing(db, store):
                print("Added quarterly pricing rule.")

        if store and not db.scalar(select(MeituanDealMapping).limit(1)):
            mappings = [
                ("100001", "知行岛4小时畅学券", RewardType.hours, 4, None, None),
                ("100002", "知行岛天卡", RewardType.day_pass, 1, None, None),
                ("100004", "知行岛月卡", RewardType.month_pass, 30, None, None),
                ("100005", "知行岛晚自习月卡", RewardType.night_monthly, 30, time(18, 0), time(23, 59, 59)),
                ("100007", "知行岛10次卡", RewardType.session, 10, None, None),
            ]
            for deal_id, name, reward_type, value, ns, ne in mappings:
                db.add(
                    MeituanDealMapping(
                        store_id=store.id,
                        deal_id=deal_id,
                        deal_name=name,
                        reward_type=reward_type,
                        reward_value=value,
                        night_start=ns,
                        night_end=ne,
                        is_active=1,
                    )
                )

        dev_user = db.scalar(select(User).where(User.openid == "dev_openid_local"))
        if dev_user and not db.scalar(
            select(Coupon).where(Coupon.user_id == dev_user.id).limit(1)
        ):
            today = date.today()
            db.add_all(
                [
                    Coupon(
                        user_id=dev_user.id,
                        coupon_name="满50减10",
                        discount_type="amount",
                        discount_val=Decimal("10.00"),
                        min_amount=Decimal("50.00"),
                        expire_date=today + timedelta(days=30),
                        status=0,
                    ),
                    Coupon(
                        user_id=dev_user.id,
                        coupon_name="9折券",
                        discount_type="percent",
                        discount_val=Decimal("10.00"),
                        min_amount=Decimal("0.00"),
                        expire_date=today + timedelta(days=30),
                        status=0,
                    ),
                ]
            )

        _backfill_invite_codes(db)

        db.commit()
        print("Seed completed.")
    finally:
        db.close()


def _backfill_invite_codes(db):
    from app.services.points import ensure_invite_code

    users = db.scalars(select(User).where(User.invite_code.is_(None))).all()
    for u in users:
        ensure_invite_code(db, u)


def _ensure_sqlite_columns():
    if "sqlite" not in str(engine.url):
        return
    stmts = [
        "ALTER TABLE users ADD COLUMN invite_code VARCHAR(20)",
        "ALTER TABLE users ADD COLUMN invited_by INTEGER",
    ]
    with engine.begin() as conn:
        for stmt in stmts:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass


if __name__ == "__main__":
    seed()
