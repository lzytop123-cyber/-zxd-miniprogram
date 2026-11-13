"""兑换门店解析：缺 store_id 时落到唯一营业店。"""

from __future__ import annotations

from fastapi import HTTPException


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, open_ids: list[int]):
        self.open_ids = open_ids

    def scalars(self, _stmt):
        return _FakeScalars(self.open_ids)


def test_explicit_store_id():
    from app.api.routes.exchange import _resolve_exchange_store_id

    assert _resolve_exchange_store_id(_FakeDB([1, 2]), 2) == 2


def test_single_open_store_autofill():
    from app.api.routes.exchange import _resolve_exchange_store_id

    assert _resolve_exchange_store_id(_FakeDB([1]), None) == 1


def test_multi_open_requires_choice():
    from app.api.routes.exchange import _resolve_exchange_store_id

    try:
        _resolve_exchange_store_id(_FakeDB([1, 2]), None)
        raise AssertionError("expected HTTPException")
    except HTTPException as ei:
        assert ei.status_code == 400
        assert "选择门店" in str(ei.detail)


def test_no_open_store():
    from app.api.routes.exchange import _resolve_exchange_store_id

    try:
        _resolve_exchange_store_id(_FakeDB([]), None)
        raise AssertionError("expected HTTPException")
    except HTTPException as ei:
        assert ei.status_code == 404


if __name__ == "__main__":
    test_explicit_store_id()
    test_single_open_store_autofill()
    test_multi_open_requires_choice()
    test_no_open_store()
    print("ok")
