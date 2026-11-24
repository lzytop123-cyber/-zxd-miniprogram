"""Leadership transitions use a fake Redis clock, without network or database I/O."""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class LeaseRedis:
    def __init__(self):
        self.now = 0
        self.value = None
        self.expires = 0

    def get(self, key):
        return self.value if self.expires > self.now else None

    def set(self, key, value, nx=False, ex=None):
        if nx and self.get(key) is not None:
            return False
        self.value, self.expires = value, self.now + ex
        return True

    def eval(self, script, count, key, token, *args):
        if self.get(key) != token:
            return 0
        if args:
            self.expires = self.now + int(args[0])
        else:
            self.value = None
        return 1


@pytest.fixture
def scheduler(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    module = importlib.import_module("app.tasks.scheduler")
    client = LeaseRedis()
    # Patch the external client factory; scheduling and lease logic remain real.
    monkeypatch.setattr(module, "get_redis", lambda: client, raising=False)
    monkeypatch.setattr(module, "_get_leader_redis", lambda: client, raising=False)
    yield module, client
    if module._scheduler is not None:
        module._scheduler.shutdown(wait=False)
        module._scheduler = None
    module._has_leadership = False


def test_worker_retries_after_stale_leader_lease_expires(scheduler):
    module, client = scheduler
    client.set("zxd:scheduler:leader", "stopped-worker", ex=120)
    module.start_scheduler()
    assert module._scheduler is not None, "Followers must retain a retry timer"
    client.now = 121
    module._maintain_leadership()
    assert client.get("zxd:scheduler:leader") not in (None, "stopped-worker")


def test_foreign_worker_cannot_extend_another_owners_lease(scheduler):
    module, client = scheduler
    client.set("zxd:scheduler:leader", "different-worker", ex=120)
    client.now = 60
    module._renew_leadership()
    client.now = 121
    assert client.get("zxd:scheduler:leader") is None


def test_redis_failure_does_not_elect_a_local_leader(scheduler, monkeypatch):
    module, _ = scheduler

    def unavailable():
        raise ConnectionError("offline")

    monkeypatch.setattr(module, "get_redis", unavailable)
    monkeypatch.setattr(module, "_get_leader_redis", unavailable)
    assert module._acquire_leadership() is False


def test_memory_redis_is_never_a_distributed_lease(scheduler, monkeypatch):
    from app.core.redis_client import MemoryRedis

    module, _ = scheduler
    monkeypatch.setattr(module, "get_redis", lambda: MemoryRedis())
    monkeypatch.setattr(module, "_get_leader_redis", lambda: MemoryRedis())
    assert module._acquire_leadership() is False


def test_stop_releases_only_the_current_owners_lock(scheduler):
    module, client = scheduler
    module.start_scheduler()
    assert client.get("zxd:scheduler:leader") is not None
    module.stop_scheduler()
    assert module._scheduler is None
    assert client.get("zxd:scheduler:leader") is None
    module.start_scheduler()
    client.set("zxd:scheduler:leader", "replacement-worker", ex=120)
    module.stop_scheduler()
    assert client.get("zxd:scheduler:leader") == "replacement-worker"


def test_business_job_stops_when_ownership_is_lost(scheduler):
    module, client = scheduler
    module.start_scheduler()
    executed = []
    client.set("zxd:scheduler:leader", "replacement-worker", ex=120)
    module._run_as_leader(lambda: executed.append("ran"))
    assert executed == []


def test_timeout_releases_only_the_cancelled_orders_coupon(scheduler, monkeypatch):
    from datetime import datetime, timedelta
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db.session import Base
    from app.models import BillType, Coupon, Reservation

    module, _ = scheduler
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(module, "SessionLocal", sessions)
    now = datetime.now()
    with sessions() as db:
        db.add(Coupon(id=1, user_id=1, status=2, reserved_order_no="expired-order"))
        db.add(Reservation(
            id=1, order_no="expired-order", user_id=1, store_id=1, seat_id=1,
            bill_type=BillType.hourly, start_time=now, end_time=now + timedelta(hours=1),
            coupon_id=1, pay_status=0, status=0, created_at=now - timedelta(minutes=16),
        ))
        db.commit()
    module.cancel_unpaid_orders()
    with sessions() as db:
        assert db.get(Reservation, 1).status == 3
        assert db.get(Coupon, 1).status == 0
        assert db.get(Coupon, 1).reserved_order_no is None
    engine.dispose()
