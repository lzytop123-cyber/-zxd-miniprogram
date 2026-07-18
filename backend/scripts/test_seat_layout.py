"""座位平面图规则回归测试。"""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models import Seat, Store
from app.services.seat_setup import SEAT_LAYOUT, ensure_store_seats, expected_seat_codes, zone_name_by_slot


def test_seat_28_is_in_immersion_zone_opposite_seat_25():
    """28 号位于沉浸区，和 25 号同排相对。"""
    assert expected_seat_codes()[-1] == "28"
    assert zone_name_by_slot(28) == "沉浸区"
    assert (28, "沉浸区", "standard", 1, 28.68, 85.5) in SEAT_LAYOUT


def test_store_seat_initialization_creates_seat_28():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        store = Store(name="测试门店")
        session.add(store)
        session.flush()

        assert ensure_store_seats(session, store) == 28
        codes = set(session.scalars(select(Seat.seat_code)).all())
        assert "28" in codes
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    test_seat_28_is_in_immersion_zone_opposite_seat_25()
    test_store_seat_initialization_creates_seat_28()
    print("seat layout checks passed")
