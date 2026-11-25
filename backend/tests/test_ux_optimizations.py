"""P0–P3 生产 UX 优化单元测试。"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_admin, get_current_user
from app.core.config import settings
from app.db.session import Base, get_db
from app.main import app
from app.models import (
    AdminUser,
    BillType,
    BleKey,
    BleLock,
    DoorLog,
    OpenType,
    PayType,
    PricingRule,
    Reservation,
    Seat,
    Store,
    User,
    WalletLog,
    Zone,
)
from app.services.booking import (
    auto_checkin_reservation,
    reservation_open_window,
    reservation_unlock_message,
)
from app.services.reservation_cancel import cancel_reservation


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_basic(db):
    store = Store(name="测试门店", status=1)
    db.add(store)
    db.flush()
    zone = Zone(store_id=store.id, name="静音区", type="quiet")
    db.add(zone)
    db.flush()
    seat = Seat(store_id=store.id, zone_id=zone.id, seat_code="A01", status=1)
    db.add(seat)
    rule = PricingRule(
        store_id=store.id,
        bill_type=BillType.hourly,
        seat_type="standard",
        price=Decimal("10.00"),
        is_active=1,
    )
    db.add(rule)
    lock = BleLock(store_id=store.id, lock_name="大门锁", lock_id="mock_lock_1", status=1)
    db.add(lock)
    user = User(
        openid="openid_ux_1",
        nickname="考研小明",
        phone="13912345678",
        balance=Decimal("50.00"),
    )
    other = User(
        openid="openid_ux_2",
        nickname="公考小红",
        phone="13887654321",
        balance=Decimal("20.00"),
    )
    admin = AdminUser(username="ux_admin", password_hash="x", role="hq", status=1)
    db.add_all([user, other, admin])
    db.commit()
    return store, zone, seat, lock, user, other, admin


def test_auto_checkin_does_not_lock_cancel_before_start(db_session):
    store, _, seat, lock, user, _, _ = _seed_basic(db_session)
    now = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
    start = now + timedelta(minutes=10)
    end = start + timedelta(hours=2)

    res = Reservation(
        order_no="UX_CANCEL_01",
        user_id=user.id,
        store_id=store.id,
        seat_id=seat.id,
        bill_type=BillType.hourly,
        start_time=start,
        end_time=end,
        duration_hours=Decimal("2.00"),
        original_price=Decimal("20.00"),
        final_price=Decimal("20.00"),
        pay_type=PayType.balance,
        pay_status=1,
        status=0,
    )
    db_session.add(res)
    db_session.commit()

    # 提前 10 分钟不自动入座，避免锁死取消
    assert auto_checkin_reservation(db_session, res, when=now) is False
    assert res.status == 0

    # 到达开始时间后才自动入座
    assert auto_checkin_reservation(db_session, res, when=start) is True
    assert res.status == 1


def test_cancel_allowed_before_start_unless_door_opened(db_session):
    store, _, seat, lock, user, _, _ = _seed_basic(db_session)
    start = datetime.now() + timedelta(minutes=20)
    end = start + timedelta(hours=2)

    # 情况1：status=1 但未到开始时间且未开门 -> 允许取消并退余额
    res1 = Reservation(
        order_no="UX_CANCEL_02",
        user_id=user.id,
        store_id=store.id,
        seat_id=seat.id,
        bill_type=BillType.hourly,
        start_time=start,
        end_time=end,
        duration_hours=Decimal("2.00"),
        original_price=Decimal("20.00"),
        final_price=Decimal("20.00"),
        pay_type=PayType.balance,
        pay_status=1,
        status=1,
    )
    db_session.add(res1)
    db_session.commit()

    msg = cancel_reservation(db_session, res1, user, "测试取消")
    assert "取消" in msg
    assert res1.status == 3
    assert res1.pay_status == 2
    assert user.balance == Decimal("70.00")

    # 情况2：status=1 且已有成功开门记录 -> 禁止取消
    res2 = Reservation(
        order_no="UX_CANCEL_03",
        user_id=user.id,
        store_id=store.id,
        seat_id=seat.id,
        bill_type=BillType.hourly,
        start_time=start,
        end_time=end,
        duration_hours=Decimal("2.00"),
        original_price=Decimal("20.00"),
        final_price=Decimal("20.00"),
        pay_type=PayType.balance,
        pay_status=1,
        status=1,
    )
    db_session.add(res2)
    db_session.flush()
    db_session.add(
        DoorLog(
            lock_id=lock.id,
            user_id=user.id,
            reservation_id=res2.id,
            open_type=OpenType.ble,
            result=1,
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        cancel_reservation(db_session, res2, user, "测试取消")
    assert exc.value.status_code == 400


def test_unlock_window_includes_late_exit_and_shows_actual_window(db_session):
    store, _, seat, _, user, _, _ = _seed_basic(db_session)
    base_day = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0)
    res = Reservation(
        order_no="UX_WIN_01",
        user_id=user.id,
        store_id=store.id,
        seat_id=seat.id,
        bill_type=BillType.hourly,
        start_time=base_day,
        end_time=base_day + timedelta(hours=2),
        pay_status=1,
        status=0,
    )
    win = reservation_open_window(res, base_day)
    assert win is not None
    assert win[0] == base_day - timedelta(minutes=15)
    assert win[1] == base_day + timedelta(hours=2, minutes=15)

    # 早于开门时间窗时提示实际可开门窗口，而不是门店全天营业时间
    msg = reservation_unlock_message(res, base_day.replace(hour=10, minute=0))
    assert msg == "13:45-16:15 可开门"


def test_extend_reservation_balance_conflict_and_insufficient(db_session):
    store, _, seat, lock, user, other, _ = _seed_basic(db_session)
    start = datetime.now() - timedelta(minutes=30)
    end = datetime.now() + timedelta(hours=1)
    res = Reservation(
        order_no="UX_EXT_01",
        user_id=user.id,
        store_id=store.id,
        seat_id=seat.id,
        bill_type=BillType.hourly,
        start_time=start,
        end_time=end,
        duration_hours=Decimal("1.50"),
        original_price=Decimal("15.00"),
        final_price=Decimal("15.00"),
        pay_type=PayType.balance,
        pay_status=1,
        status=1,
    )
    db_session.add(res)
    db_session.flush()
    ble_key = BleKey(
        lock_id=lock.id,
        reservation_id=res.id,
        user_id=user.id,
        lock_data="mock_data",
        start_time=start - timedelta(minutes=15),
        end_time=end + timedelta(minutes=15),
        status=1,
    )
    db_session.add(ble_key)
    db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        client = TestClient(app)
        # 成功续时 2 小时（20 元）
        resp = client.post(
            f"/api/reservation/{res.id}/extend",
            json={"extra_hours": 2, "pay_type": "balance"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["extra_amount"] == 20.0
        db_session.refresh(res)
        db_session.refresh(user)
        db_session.refresh(ble_key)
        assert res.end_time == end + timedelta(hours=2)
        assert res.final_price == Decimal("35.00")
        assert user.balance == Decimal("30.00")
        assert ble_key.end_time == res.end_time + timedelta(minutes=15)
        logs = db_session.scalars(
            select(WalletLog).where(WalletLog.ref_order == res.order_no)
        ).all()
        assert len(logs) == 1

        # 余额不足（需要 50 元，当前余额 30 元）
        resp_low = client.post(
            f"/api/reservation/{res.id}/extend",
            json={"extra_hours": 5, "pay_type": "balance"},
        )
        assert resp_low.status_code == 400
        assert "余额不足" in resp_low.json()["detail"]

        # 后续时段已被他人占用 -> 409 冲突
        conflict_res = Reservation(
            order_no="UX_EXT_CONFLICT",
            user_id=other.id,
            store_id=store.id,
            seat_id=seat.id,
            bill_type=BillType.hourly,
            start_time=res.end_time + timedelta(minutes=10),
            end_time=res.end_time + timedelta(hours=2),
            pay_type=PayType.balance,
            pay_status=1,
            status=0,
        )
        db_session.add(conflict_res)
        db_session.commit()
        resp_conflict = client.post(
            f"/api/reservation/{res.id}/extend",
            json={"extra_hours": 1, "pay_type": "balance"},
        )
        assert resp_conflict.status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_global_exception_handlers_422_and_500(db_session):
    _, _, _, _, user, _, _ = _seed_basic(db_session)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user

    @app.get("/api/_test_crash_500")
    def _boom():
        raise RuntimeError("secret internal database credentials")

    try:
        client = TestClient(app, raise_server_exceptions=False)
        # 422 参数校验异常
        r422 = client.post("/api/reservation/1/extend", json={"extra_hours": "not-an-int"})
        assert r422.status_code == 422
        assert r422.json() == {
            "code": 422,
            "message": "参数格式有误，请检查后重试",
            "data": None,
        }

        # 500 未捕获异常不泄露堆栈
        r500 = client.get("/api/_test_crash_500")
        assert r500.status_code == 500
        assert r500.json() == {
            "code": 500,
            "message": "服务暂时开小差了，请稍后重试",
            "data": None,
        }
        assert "secret" not in r500.text
    finally:
        app.dependency_overrides.clear()


def test_admin_keyword_search_reservations_and_door_logs(db_session, monkeypatch):
    import app.api.admin_role_guard as guard_mod

    store, _, seat, lock, user, other, admin = _seed_basic(db_session)
    monkeypatch.setattr(guard_mod, "_load_admin", lambda _req: admin)
    now = datetime.now()
    r1 = Reservation(
        order_no="ORD_ALPHA_1001",
        user_id=user.id,
        store_id=store.id,
        seat_id=seat.id,
        bill_type=BillType.hourly,
        start_time=now,
        end_time=now + timedelta(hours=2),
        pay_type=PayType.balance,
        pay_status=1,
        status=1,
    )
    r2 = Reservation(
        order_no="ORD_BETA_2002",
        user_id=other.id,
        store_id=store.id,
        seat_id=seat.id,
        bill_type=BillType.hourly,
        start_time=now + timedelta(hours=3),
        end_time=now + timedelta(hours=5),
        pay_type=PayType.balance,
        pay_status=1,
        status=0,
    )
    db_session.add_all([r1, r2])
    db_session.flush()
    db_session.add_all(
        [
            DoorLog(lock_id=lock.id, user_id=user.id, reservation_id=r1.id, open_type=OpenType.ble, result=1),
            DoorLog(lock_id=lock.id, user_id=other.id, reservation_id=r2.id, open_type=OpenType.ble, result=1),
        ]
    )
    db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_admin] = lambda: admin
    try:
        client = TestClient(app)
        # 按手机号搜预约
        res_phone = client.get("/api/admin/reservations", params={"keyword": "1391234"})
        assert res_phone.status_code == 200
        assert res_phone.json()["data"]["total"] == 1
        assert res_phone.json()["data"]["items"][0]["order_no"] == "ORD_ALPHA_1001"

        # 按昵称搜预约
        res_nick = client.get("/api/admin/reservations", params={"keyword": "小红"})
        assert res_nick.status_code == 200
        assert res_nick.json()["data"]["total"] == 1
        assert res_nick.json()["data"]["items"][0]["order_no"] == "ORD_BETA_2002"

        # 按订单号搜预约
        res_ord = client.get("/api/admin/reservations", params={"keyword": "ALPHA"})
        assert res_ord.status_code == 200
        assert res_ord.json()["data"]["total"] == 1

        # 按手机号/昵称搜开门记录
        logs_phone = client.get("/api/admin/door-logs", params={"keyword": "1388765"})
        assert logs_phone.status_code == 200
        assert logs_phone.json()["data"]["total"] == 1
        assert logs_phone.json()["data"]["items"][0]["user_nickname"] == "公考小红"
    finally:
        app.dependency_overrides.clear()


def test_face_upload_saves_short_path_and_subscribe_config(db_session, monkeypatch):
    _, _, _, _, user, _, _ = _seed_basic(db_session)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(settings, "wx_subscribe_card_expire_tmpl_id", "TMPL_CARD")
    monkeypatch.setattr(settings, "wx_subscribe_booking_confirm_tmpl_id", "TMPL_BOOK")
    monkeypatch.setattr(settings, "wx_subscribe_expiring_soon_tmpl_id", "TMPL_EXP")
    monkeypatch.setattr(settings, "wx_subscribe_checkout_tmpl_id", "")

    try:
        client = TestClient(app)
        payload = "data:image/jpeg;base64," + base64.b64encode(b"fake-face-bytes").decode()
        resp = client.post("/api/user/face", json={"face_image": payload})
        assert resp.status_code == 200
        db_session.refresh(user)
        assert user.face_image is not None
        assert user.face_image.startswith("/static/faces/")
        assert len(user.face_image) <= 500

        cfg = client.get("/api/user/subscribe-config")
        assert cfg.status_code == 200
        data = cfg.json()["data"]
        assert data["card_expire_tmpl_id"] == "TMPL_CARD"
        assert data["booking_confirm_tmpl_id"] == "TMPL_BOOK"
        assert data["expiring_soon_tmpl_id"] == "TMPL_EXP"
        assert data["checkout_tmpl_id"] is None
        assert data["enabled_tmpl_ids"] == ["TMPL_CARD", "TMPL_BOOK", "TMPL_EXP"]
        assert data["enabled"] is True
    finally:
        app.dependency_overrides.clear()
