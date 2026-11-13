"""兑换门店解析：默认门店配置 + 唯一营业店兜底。"""

from __future__ import annotations

from fastapi import HTTPException


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, open_ids: list[int], default_store_id: int | None = None):
        self.open_ids = open_ids
        self._setting = type("S", (), {"default_store_id": default_store_id})()

    def scalars(self, _stmt):
        return _FakeScalars(self.open_ids)

    def get(self, model, key):
        name = getattr(model, "__name__", str(model))
        if "SiteExchangeSetting" in name and key == 1:
            return self._setting
        return None


def test_explicit_store_id():
    from app.services.exchange_setting import resolve_exchange_store_id

    assert resolve_exchange_store_id(_FakeDB([1, 2]), 2) == 2


def test_configured_default_when_open():
    from app.services.exchange_setting import resolve_exchange_store_id

    assert resolve_exchange_store_id(_FakeDB([1, 2], default_store_id=2), None) == 2


def test_configured_default_ignored_if_closed():
    from app.services.exchange_setting import resolve_exchange_store_id

    assert resolve_exchange_store_id(_FakeDB([1], default_store_id=2), None) == 1


def test_single_open_store_autofill():
    from app.services.exchange_setting import resolve_exchange_store_id

    assert resolve_exchange_store_id(_FakeDB([1]), None) == 1


def test_multi_open_requires_choice():
    from app.services.exchange_setting import resolve_exchange_store_id

    try:
        resolve_exchange_store_id(_FakeDB([1, 2]), None)
        raise AssertionError("expected HTTPException")
    except HTTPException as ei:
        assert ei.status_code == 400
        assert "选择门店" in str(ei.detail)


def test_no_open_store():
    from app.services.exchange_setting import resolve_exchange_store_id

    try:
        resolve_exchange_store_id(_FakeDB([]), None)
        raise AssertionError("expected HTTPException")
    except HTTPException as ei:
        assert ei.status_code == 404


if __name__ == "__main__":
    test_explicit_store_id()
    test_configured_default_when_open()
    test_configured_default_ignored_if_closed()
    test_single_open_store_autofill()
    test_multi_open_requires_choice()
    test_no_open_store()
    print("ok")
