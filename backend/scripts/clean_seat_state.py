"""清理座位占用状态：删除预约及相关钥匙/开门记录，并重置座位为启用。"""

from sqlalchemy import delete, func, select, update

from app.db.session import SessionLocal
from app.models import BleKey, DoorLog, Reservation, Seat


def clean_seat_state(*, clear_all_reservations: bool = True) -> dict:
    db = SessionLocal()
    try:
        before = {
            "reservations": db.scalar(select(func.count()).select_from(Reservation)) or 0,
            "ble_keys": db.scalar(select(func.count()).select_from(BleKey)) or 0,
            "door_logs": db.scalar(
                select(func.count()).select_from(DoorLog).where(DoorLog.reservation_id.isnot(None))
            )
            or 0,
            "seats_disabled": db.scalar(select(func.count()).select_from(Seat).where(Seat.status != 1)) or 0,
        }

        if clear_all_reservations:
            db.execute(delete(DoorLog).where(DoorLog.reservation_id.isnot(None)))
            db.execute(delete(BleKey))
            db.execute(delete(Reservation))
        else:
            db.execute(
                delete(DoorLog).where(
                    DoorLog.reservation_id.in_(select(Reservation.id).where(Reservation.status.in_([0, 1])))
                )
            )
            db.execute(
                delete(BleKey).where(
                    BleKey.reservation_id.in_(select(Reservation.id).where(Reservation.status.in_([0, 1])))
                )
            )
            db.execute(delete(Reservation).where(Reservation.status.in_([0, 1])))

        db.execute(update(Seat).values(status=1))
        db.commit()

        after = {
            "reservations": db.scalar(select(func.count()).select_from(Reservation)) or 0,
            "ble_keys": db.scalar(select(func.count()).select_from(BleKey)) or 0,
            "door_logs": db.scalar(
                select(func.count()).select_from(DoorLog).where(DoorLog.reservation_id.isnot(None))
            )
            or 0,
            "seats_disabled": db.scalar(select(func.count()).select_from(Seat).where(Seat.status != 1)) or 0,
        }
        return {"before": before, "after": after}
    finally:
        db.close()


if __name__ == "__main__":
    result = clean_seat_state(clear_all_reservations=True)
    print("Seat state cleaned.")
    print("Before:", result["before"])
    print("After:", result["after"])
