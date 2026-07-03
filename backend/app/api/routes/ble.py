from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_current_user
from app.core.redis_client import cache_get
from app.db.session import get_db
from app.models import BleBatteryAlert, BleKey, BleLock, DoorLog, OpenType, Reservation, User
from app.schemas.common import ResponseModel
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
        ttlock_configured = bool(settings.ttlock_client_id and settings.ttlock_client_secret)
        return ResponseModel(
            data={
                "reservationId": reservation_id,
                "lockData": cached,
                "lockName": lock.lock_name if lock else None,
                "gatewayUnlock": ttlock_configured
                and lock
                and lock.lock_id
                and not str(lock.lock_id).startswith("mock_"),
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
    ttlock_configured = bool(settings.ttlock_client_id and settings.ttlock_client_secret)
    return ResponseModel(
        data={
            "reservationId": reservation_id,
            "lockData": ble_key.lock_data,
            "lockName": lock.lock_name if lock else None,
            "gatewayUnlock": ttlock_configured and lock and lock.lock_id and not str(lock.lock_id).startswith("mock_"),
            "blePlugin": True,
        }
    )


@router.post("/ble/unlock/{reservation_id}", response_model=ResponseModel)
async def remote_unlock_door(
    reservation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """通过 WiFi 网关远程开锁（无需蓝牙插件，个体户可用）。"""
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

    log = DoorLog(
        lock_id=ble_key.lock_id,
        user_id=user.id,
        reservation_id=reservation_id,
        open_type=OpenType.ble,
        result=1 if body.result == "success" else 0,
        fail_reason=body.error_msg,
    )
    if body.result == "success":
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
