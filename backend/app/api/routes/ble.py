from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_current_user
from app.core.redis_client import cache_get
from app.db.session import get_db
from app.models import BleBatteryAlert, BleKey, BleLock, DoorLog, OpenType, Reservation, User
from app.schemas.common import PageResult, ResponseModel
from app.core.config import settings
from app.services.business import TTLockService
from app.services.booking import auto_checkin_reservation, reservation_unlock_allowed, reservation_unlock_message

router = APIRouter(tags=["蓝牙"])


class DoorLogRequest(BaseModel):
    reservation_id: int
    result: str
    error_code: str | None = None
    error_msg: str | None = None


class BleLockCreate(BaseModel):
    store_id: int
    lock_name: str
    lock_id: str
    mac_address: str | None = None
    lock_data: str | None = None


class BleLockUpdate(BaseModel):
    lock_name: str | None = None
    lock_id: str | None = None
    mac_address: str | None = None
    lock_data: str | None = None
    status: int | None = None


@router.get("/ble/key/{reservation_id}", response_model=ResponseModel)
def get_ble_key(
    reservation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reservation = db.get(Reservation, reservation_id)
    if not reservation or reservation.user_id != user.id:
        raise HTTPException(status_code=404, detail="订单不存在")
    if reservation.pay_status != 1:
        raise HTTPException(status_code=400, detail="订单未支付")
    if not reservation_unlock_allowed(reservation):
        detail = reservation_unlock_message(reservation) or "当前无法开门"
        raise HTTPException(status_code=400, detail=detail)

    cached = cache_get(f"ble_key:{reservation_id}")
    if cached:
        ble_key = db.scalar(
            select(BleKey).where(
                BleKey.reservation_id == reservation_id,
                BleKey.user_id == user.id,
                BleKey.status == 1,
            )
        )
        lock = db.get(BleLock, ble_key.lock_id) if ble_key else None
        return ResponseModel(
            data={
                "reservationId": reservation_id,
                "lockData": cached,
                "lockName": lock.lock_name if lock else None,
                "blePlugin": True,
            }
        )

    ble_key = db.scalar(
        select(BleKey).where(
            BleKey.reservation_id == reservation_id,
            BleKey.user_id == user.id,
            BleKey.status == 1,
        )
    )
    if not ble_key or not ble_key.lock_data:
        raise HTTPException(status_code=404, detail="蓝牙钥匙未生成")

    lock = db.get(BleLock, ble_key.lock_id)
    return ResponseModel(
        data={
            "reservationId": reservation_id,
            "lockData": ble_key.lock_data,
            "lockName": lock.lock_name if lock else None,
            "blePlugin": True,
        }
    )


@router.post("/ble/unlock/{reservation_id}", response_model=ResponseModel)
async def remote_unlock_door(
    reservation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """通过 WiFi 网关远程开锁（需门锁绑定网关，默认关闭）。"""
    if not settings.ttlock_remote_unlock_enabled:
        raise HTTPException(status_code=501, detail="门店门锁不支持远程开门，请使用蓝牙开门")
    reservation = db.get(Reservation, reservation_id)
    if not reservation or reservation.user_id != user.id:
        raise HTTPException(status_code=404, detail="订单不存在")
    if reservation.pay_status != 1:
        raise HTTPException(status_code=400, detail="订单未支付")

    if not reservation_unlock_allowed(reservation):
        detail = reservation_unlock_message(reservation) or "当前无法开门"
        raise HTTPException(status_code=400, detail=detail)

    ble_key = db.scalar(
        select(BleKey).where(
            BleKey.reservation_id == reservation_id,
            BleKey.user_id == user.id,
            BleKey.status == 1,
        )
    )
    if not ble_key:
        raise HTTPException(status_code=404, detail="钥匙不存在")

    lock = db.get(BleLock, ble_key.lock_id)
    if not lock or not lock.lock_id:
        raise HTTPException(status_code=400, detail="门店未配置门锁")

    try:
        if str(lock.lock_id).startswith("mock_"):
            result = {"mock": True}
        else:
            result = await TTLockService.remote_unlock(str(lock.lock_id))
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    log = DoorLog(
        lock_id=ble_key.lock_id,
        user_id=user.id,
        reservation_id=reservation_id,
        open_type=OpenType.remote,
        result=1,
    )
    ble_key.used_at = datetime.now()
    auto_checkin_reservation(db, reservation)
    db.add(log)
    db.commit()
    return ResponseModel(message="开门成功", data={"result": result})


@router.post("/ble/checkin/{reservation_id}", response_model=ResponseModel)
def report_door_log(
    reservation_id: int,
    body: DoorLogRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ble_key = db.scalar(
        select(BleKey).where(BleKey.reservation_id == reservation_id, BleKey.user_id == user.id)
    )
    if not ble_key:
        raise HTTPException(status_code=404, detail="钥匙不存在")

    reservation = db.get(Reservation, reservation_id)
    if not reservation or reservation.user_id != user.id:
        raise HTTPException(status_code=404, detail="订单不存在")

    log = DoorLog(
        lock_id=ble_key.lock_id,
        user_id=user.id,
        reservation_id=reservation_id,
        open_type=OpenType.ble,
        result=1 if body.result == "success" else 0,
        fail_reason=body.error_msg,
    )
    if body.result == "success":
        if reservation.pay_status != 1:
            raise HTTPException(status_code=400, detail="订单未支付")
        if not reservation_unlock_allowed(reservation):
            detail = reservation_unlock_message(reservation) or "当前无法开门"
            raise HTTPException(status_code=400, detail=detail)
        ble_key.used_at = datetime.now()
        lock = db.get(BleLock, ble_key.lock_id)
        if lock and lock.battery_level is not None and lock.battery_level > 0:
            lock.battery_level = max(lock.battery_level - 1, 0)
        if reservation:
            auto_checkin_reservation(db, reservation)
    db.add(log)
    db.commit()
    return ResponseModel(message="记录成功")


def _lock_to_dict(lock: BleLock) -> dict:
    return {
        "id": lock.id,
        "store_id": lock.store_id,
        "lock_name": lock.lock_name,
        "lock_type": lock.lock_type.value if lock.lock_type else None,
        "brand": lock.brand,
        "lock_id": lock.lock_id,
        "mac_address": lock.mac_address,
        "battery_level": lock.battery_level,
        "status": lock.status,
    }


@router.get("/admin/locks", response_model=ResponseModel)
def admin_list_locks(
    store_id: int | None = None,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = select(BleLock)
    if store_id:
        query = query.where(BleLock.store_id == store_id)
    locks = db.scalars(query).all()
    return ResponseModel(data=[_lock_to_dict(lock) for lock in locks])


_OPEN_TYPE_LABELS = {
    "ble": "蓝牙",
    "remote": "远程",
    "admin": "管理员",
    "auto": "自动",
}


@router.get("/admin/door-logs", response_model=ResponseModel)
def admin_list_door_logs(
    lock_id: int | None = None,
    result: int | None = Query(None, description="1成功 0失败"),
    date_from: str | None = Query(None, description="YYYY-MM-DD"),
    date_to: str | None = Query(None, description="YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = select(DoorLog)
    if lock_id is not None:
        query = query.where(DoorLog.lock_id == lock_id)
    if result is not None:
        query = query.where(DoorLog.result == result)
    if date_from:
        try:
            start = datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError as e:
            raise HTTPException(status_code=400, detail="date_from 格式应为 YYYY-MM-DD") from e
        query = query.where(DoorLog.opened_at >= start)
    if date_to:
        try:
            end = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="date_to 格式应为 YYYY-MM-DD") from e
        query = query.where(DoorLog.opened_at < end)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(DoorLog.opened_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = []
    for log in rows:
        lock = db.get(BleLock, log.lock_id)
        user = db.get(User, log.user_id) if log.user_id else None
        reservation = db.get(Reservation, log.reservation_id) if log.reservation_id else None
        open_type = log.open_type.value if log.open_type else None
        items.append(
            {
                "id": log.id,
                "opened_at": log.opened_at.isoformat(sep=" ", timespec="seconds") if log.opened_at else None,
                "lock_id": log.lock_id,
                "lock_name": lock.lock_name if lock else None,
                "user_id": log.user_id,
                "user_nickname": user.nickname if user else None,
                "user_phone": user.phone if user else None,
                "reservation_id": log.reservation_id,
                "order_no": reservation.order_no if reservation else None,
                "open_type": open_type,
                "open_type_label": _OPEN_TYPE_LABELS.get(open_type or "", open_type),
                "result": log.result,
                "fail_reason": log.fail_reason,
            }
        )

    return ResponseModel(
        data=PageResult(items=items, total=total, page=page, page_size=page_size)
    )


@router.post("/admin/locks", response_model=ResponseModel)
def admin_create_lock(
    body: BleLockCreate,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    lock = BleLock(**body.model_dump())
    db.add(lock)
    db.commit()
    db.refresh(lock)
    return ResponseModel(data=_lock_to_dict(lock))


@router.put("/admin/locks/{lock_id}", response_model=ResponseModel)
def admin_update_lock(
    lock_id: int,
    body: BleLockUpdate,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    lock = db.get(BleLock, lock_id)
    if not lock:
        raise HTTPException(status_code=404, detail="门锁不存在")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(lock, field, value)
    db.commit()
    db.refresh(lock)
    return ResponseModel(message="已更新", data=_lock_to_dict(lock))


@router.get("/admin/locks/alerts", response_model=ResponseModel)
def admin_lock_alerts(_: object = Depends(get_current_admin), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(BleBatteryAlert)
        .where(BleBatteryAlert.is_read == 0)
        .order_by(BleBatteryAlert.created_at.desc())
        .limit(20)
    ).all()
    data = []
    for alert in rows:
        lock = db.get(BleLock, alert.lock_id)
        data.append(
            {
                "id": alert.id,
                "lock_id": alert.lock_id,
                "lock_name": lock.lock_name if lock else None,
                "battery_level": alert.battery_level,
                "message": alert.message,
                "created_at": alert.created_at.isoformat() if alert.created_at else None,
            }
        )
    return ResponseModel(data=data)


@router.post("/admin/locks/alerts/{alert_id}/read", response_model=ResponseModel)
def read_lock_alert(
    alert_id: int,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    alert = db.get(BleBatteryAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    alert.is_read = 1
    db.commit()
    return ResponseModel(message="已标记已读")


@router.post("/admin/locks/{lock_id}/refresh-battery", response_model=ResponseModel)
async def refresh_battery(
    lock_id: int,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    lock = db.get(BleLock, lock_id)
    if not lock:
        raise HTTPException(status_code=404, detail="门锁不存在")
    # 生产环境调用 TTLock API 查询电量
    lock.battery_level = lock.battery_level or 100
    db.commit()
    return ResponseModel(data={"battery_level": lock.battery_level})
