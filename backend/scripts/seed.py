"""Database seed script for development."""

from datetime import date, time, timedelta
from decimal import Decimal

from sqlalchemy import select, text

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.services.schema_migrate import run_schema_migrations
from app.services.seat_setup import ensure_store_seats
from app.data.deal_templates import DEAL_MAPPING_TEMPLATES
from app.models import (
    AdminUser,
    BillType,
    BleLock,
    Coupon,
    MeituanDealMapping,
    HomeBanner,
    HomeCarouselSetting,
    PricingRule,
    RewardType,
    Seat,
    Store,
    User,
    Zone,
)


# 云老板验券返回的 dealId → 期限卡权益（美团后台 ID 可能不同，以验券返回为准）
REAL_DEAL_MAPPINGS = DEAL_MAPPING_TEMPLATES


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
        row.valid_days = 10
        row.min_hours = None
        row.max_hours = None
        return False
    db.add(
        PricingRule(
            store_id=store.id,
            bill_type=BillType.session,
            seat_type="standard",
            price=Decimal("58.00"),
            valid_days=10,
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
    db = SessionLocal()
    try:
        run_schema_migrations(db)
        if not db.scalar(select(Store).limit(1)):
            store = Store(
                name="知行岛·自习室",
                address="太原市万柏林区融创长风壹号3号公寓2单元B604室",
                latitude=Decimal("37.820712"),
                longitude=Decimal("112.517856"),
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

            ensure_store_seats(db, store)

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
            added = ensure_store_seats(db, store)
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
                ("100005", "知行岛晚自习月卡", RewardType.night_monthly, 30, time(18, 0), time(23, 30)),
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
        _ensure_home_banner(db)
        _ensure_carousel_settings(db)

        db.commit()
        print("Seed completed.")
    finally:
        db.close()


def _backfill_invite_codes(db):
    from app.services.points import ensure_invite_code

    users = db.scalars(select(User).where(User.invite_code.is_(None))).all()
    for u in users:
        ensure_invite_code(db, u)


def _ensure_carousel_settings(db) -> None:
    row = db.get(HomeCarouselSetting, 1)
    if not row:
        db.add(HomeCarouselSetting(id=1, hero_height=680, hero_mode="fullscreen"))
        return
    if not row.hero_height or row.hero_height <= 520:
        row.hero_height = 680
    if not row.hero_mode:
        row.hero_mode = "fullscreen"


def _ensure_home_banner(db) -> None:
    if db.scalar(select(HomeBanner).limit(1)):
        return
    db.add(
        HomeBanner(
            ribbon="夏日专注计划",
            title_line1="上岛泡一个",
            title_line2="高效的夏天",
            date_label="活动期",
            date_range="07.01 — 08.31",
            cta_text="立即开启",
            is_active=1,
            sort_order=0,
        )
    )


if __name__ == "__main__":
    seed()
