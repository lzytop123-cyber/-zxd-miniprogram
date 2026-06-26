import hashlib
import time
from datetime import datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.redis_client import cache_get, cache_set
from app.models import (
    BillType,
    BleKey,
    BleLock,
    PricingRule,
    Reservation,
    Seat,
    StudyStat,
    User,
)


class WechatService:
    @staticmethod
    async def code_to_openid(code: str) -> dict:
        use_dev_login = (
            settings.app_env == "development" and settings.wx_appid.startswith("your_")
        ) or (settings.pre_wechat_launch and not settings.wx_login_configured)
        if use_dev_login:
            # 固定 openid，避免每次 wx.login 换用户导致看不到自己的订单
            return {"openid": "dev_openid_local", "session_key": "dev_session"}

        url = "https://api.weixin.qq.com/sns/jscode2session"
        params = {
            "appid": settings.wx_appid,
            "secret": settings.wx_app_secret,
            "js_code": code,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
        if "openid" not in data:
            raise ValueError(data.get("errmsg", "微信登录失败"))
        return data

    @staticmethod
    async def get_access_token() -> str:
        cached = cache_get("wx:access_token")
        if cached:
            return cached
        url = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": settings.wx_appid,
            "secret": settings.wx_app_secret,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
        token = data.get("access_token")
        if not token:
            raise ValueError(data.get("errmsg", "获取 access_token 失败"))
        cache_set("wx:access_token", token, 7000)
        return token

    @staticmethod
    async def get_phone_number(code: str) -> str:
        if settings.app_env == "development" or (
            settings.pre_wechat_launch and not settings.wx_login_configured
        ):
            return "13800000000"
        token = await WechatService.get_access_token()
        url = f"https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token={token}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={"code": code})
            data = resp.json()
        phone = data.get("phone_info", {}).get("phoneNumber")
        if not phone:
            raise ValueError(data.get("errmsg", "获取手机号失败"))
        return phone


class TTLockService:
    BASE_URL = "https://cnapi.ttlock.com"

    @staticmethod
    def _password_md5(raw: str) -> str:
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _api_error(data: dict, default: str = "TTLock 请求失败") -> None:
        code = data.get("errcode", data.get("errorCode", 0))
        if code not in (0, None, "0"):
            raise ValueError(data.get("errmsg") or data.get("description") or default)

    @staticmethod
    async def get_access_token() -> str:
        cached = cache_get("ttlock:access_token")
        if cached:
            return cached
        if not settings.ttlock_client_id:
            return "mock_token"

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{TTLockService.BASE_URL}/oauth2/token",
                data={
                    "grant_type": "password",
                    "clientId": settings.ttlock_client_id,
                    "clientSecret": settings.ttlock_client_secret,
                    "username": settings.ttlock_username,
                    "password": TTLockService._password_md5(settings.ttlock_password),
                },
            )
            data = resp.json()
        token = data.get("access_token")
        if not token:
            code = data.get("errcode", data.get("errorCode"))
            msg = data.get("errmsg") or data.get("description") or "TTLock 认证失败"
            if code:
                msg = f"[{code}] {msg}"
            raise ValueError(msg)
        cache_set("ttlock:access_token", token, 7000)
        return token

    @staticmethod
    async def get_ekey(lock_id: str) -> dict:
        """获取锁的电子钥匙信息（含 lockData）。"""
        if not settings.ttlock_client_id or not lock_id:
            return {}
        token = await TTLockService.get_access_token()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{TTLockService.BASE_URL}/v3/key/get",
                data={
                    "clientId": settings.ttlock_client_id,
                    "accessToken": token,
                    "lockId": lock_id,
                    "date": int(time.time() * 1000),
                },
            )
            data = resp.json()
        TTLockService._api_error(data, "获取钥匙失败")
        return data

    @staticmethod
    async def remote_unlock(lock_id: str) -> dict:
        """通过 WiFi 网关远程开锁（个体户可用，无需小程序蓝牙插件）。"""
        if not settings.ttlock_client_id or not lock_id:
            return {"mock": True}
        token = await TTLockService.get_access_token()
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{TTLockService.BASE_URL}/v3/lock/unlock",
                data={
                    "clientId": settings.ttlock_client_id,
                    "accessToken": token,
                    "lockId": lock_id,
                    "date": int(time.time() * 1000),
                },
            )
            data = resp.json()
        TTLockService._api_error(data, "远程开锁失败")
        return data

    @staticmethod
    async def send_key(lock: BleLock, start: datetime, end: datetime, key_name: str) -> dict:
        if not settings.ttlock_client_id or not lock.lock_id or str(lock.lock_id).startswith("mock_"):
            return {
                "keyId": f"mock_{lock.id}_{int(time.time())}",
                "lockData": lock.lock_data or f"mock_lock_data_{lock.id}",
            }

        token = await TTLockService.get_access_token()
        now_ms = int(time.time() * 1000)
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{TTLockService.BASE_URL}/v3/key/send",
                data={
                    "clientId": settings.ttlock_client_id,
                    "accessToken": token,
                    "lockId": lock.lock_id,
                    "receiverUsername": settings.ttlock_username,
                    "keyName": key_name,
                    "startDate": int(start.timestamp() * 1000),
                    "endDate": int(end.timestamp() * 1000),
                    "date": now_ms,
                },
            )
            data = resp.json()
        TTLockService._api_error(data, "发放蓝牙钥匙失败")

        lock_data = data.get("lockData") or lock.lock_data
        if not lock_data:
            ekey = await TTLockService.get_ekey(str(lock.lock_id))
            lock_data = ekey.get("lockData") or lock.lock_data
        return {
            "keyId": data.get("keyId", ""),
            "lockData": lock_data,
        }

    @staticmethod
    async def delete_key(key_id: str) -> None:
        if not settings.ttlock_client_id or not key_id or str(key_id).startswith("mock_"):
            return
        token = await TTLockService.get_access_token()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{TTLockService.BASE_URL}/v3/key/delete",
                data={
                    "clientId": settings.ttlock_client_id,
                    "accessToken": token,
                    "keyId": key_id,
                    "date": int(time.time() * 1000),
                },
            )
            data = resp.json()
        TTLockService._api_error(data, "删除钥匙失败")


def generate_order_no() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + str(int(time.time() * 1000))[-6:]


def calc_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return round(6371 * 2 * asin(sqrt(a)), 2)


def _seat_conflict_query(seat_id: int, start: datetime, end: datetime):
    """仅将未过期、仍有效的预约视为占用。"""
    now = datetime.now()
    return select(Reservation).where(
        Reservation.seat_id == seat_id,
        Reservation.status.in_([0, 1]),
        Reservation.pay_status.in_([0, 1]),
        Reservation.end_time > now,
        Reservation.start_time < end,
        Reservation.end_time > start,
    )


def get_seat_status(db: Session, seat_id: int, at: datetime | None = None) -> str:
    at = at or datetime.now()
    seat = db.get(Seat, seat_id)
    if not seat or seat.status != 1:
        return "disabled"

    active = db.scalar(
        select(Reservation).where(
            Reservation.seat_id == seat_id,
            Reservation.pay_status == 1,
            Reservation.status.in_([0, 1]),
            Reservation.start_time <= at,
            Reservation.end_time > at,
        )
    )
    if active:
        return "occupied" if active.status == 1 else "reserved"

    upcoming = db.scalar(
        select(Reservation).where(
            Reservation.seat_id == seat_id,
            Reservation.pay_status.in_([0, 1]),
            Reservation.status == 0,
            Reservation.end_time > at,
            Reservation.start_time > at,
            Reservation.start_time <= at + timedelta(hours=2),
        )
    )
    return "reserved" if upcoming else "available"


def find_available_seat(
    db: Session, store_id: int, start: datetime, end: datetime, seat_type: str | None = None
) -> Seat | None:
    query = select(Seat).where(
        Seat.store_id == store_id,
        Seat.status == 1,
        Seat.is_buffer == 0,
    )
    if seat_type:
        query = query.where(Seat.seat_type == seat_type)
    seats = db.scalars(query).all()

    for seat in seats:
        conflict = db.scalar(_seat_conflict_query(seat.id, start, end))
        if not conflict:
            return seat
    return None


def calc_price(
    db: Session, store_id: int, bill_type: BillType, duration_hours: Decimal, seat_type: str = "standard"
) -> tuple[Decimal, PricingRule | None]:
    rule = db.scalar(
        select(PricingRule).where(
            PricingRule.store_id == store_id,
            PricingRule.bill_type == bill_type,
            PricingRule.seat_type == seat_type,
            PricingRule.is_active == 1,
        )
    )
    if not rule:
        raise ValueError("未配置价格规则")

    if bill_type in (BillType.hourly, BillType.session):
        if bill_type == BillType.session:
            days = int(duration_hours)
            if days < 1:
                raise ValueError("至少预约1天")
            price = rule.price * days
        else:
            if rule.min_hours and duration_hours < rule.min_hours:
                raise ValueError(f"最少预约 {rule.min_hours} 小时")
            if rule.max_hours and duration_hours > rule.max_hours:
                raise ValueError(f"最多预约 {rule.max_hours} 小时")
            price = rule.price * duration_hours
    else:
        price = rule.price
    return price, rule


def update_study_title(user: User, total_minutes: int) -> None:
    hours = total_minutes / 60
    if hours < 10:
        user.title = "小白"
    elif hours < 50:
        user.title = "学徒"
    elif hours < 200:
        user.title = "学者"
    elif hours < 500:
        user.title = "学霸"
    else:
        user.title = "大师"


async def create_ble_keys_for_reservation(db: Session, reservation: Reservation) -> list[BleKey]:
    locks = db.scalars(
        select(BleLock).where(BleLock.store_id == reservation.store_id, BleLock.status == 1)
    ).all()
    if not locks:
        return []

    keys: list[BleKey] = []
    key_start = reservation.start_time - timedelta(minutes=15)
    key_end = reservation.end_time + timedelta(minutes=15)
    for lock in locks:
        try:
            result = await TTLockService.send_key(
                lock,
                key_start,
                key_end,
                f"知行岛-{reservation.order_no}",
            )
        except ValueError as e:
            if not lock.lock_data:
                continue
            result = {
                "keyId": f"fallback_{lock.id}_{int(time.time())}",
                "lockData": lock.lock_data,
            }
        lock_data = result.get("lockData")
        if not lock_data:
            continue
        ble_key = BleKey(
            lock_id=lock.id,
            reservation_id=reservation.id,
            user_id=reservation.user_id,
            ttlock_key_id=str(result.get("keyId", "")),
            lock_data=lock_data,
            start_time=key_start,
            end_time=key_end,
        )
        db.add(ble_key)
        keys.append(ble_key)
        expire = int((reservation.end_time - datetime.now()).total_seconds()) + 3600
        if expire > 0:
            cache_set(f"ble_key:{reservation.id}", lock_data, expire)
    if keys:
        db.commit()
    return keys
