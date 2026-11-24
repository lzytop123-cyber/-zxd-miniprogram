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


def test_deal_name_picks_ligongda():
    from app.services.exchange_setting import infer_store_from_deal_name

    stores = [
        type("S", (), {"id": 1, "name": "知行岛自习室(千峰南路店)"})(),
        type("S", (), {"id": 2, "name": "知行岛自习室(理工大店)"})(),
    ]
    hit = infer_store_from_deal_name(stores, "理工大店团购四小时")
    assert hit.id == 2


def test_deal_name_picks_qianfeng_short():
    from app.services.exchange_setting import infer_store_from_deal_name

    stores = [
        type("S", (), {"id": 1, "name": "知行岛自习室(千峰南路店)"})(),
        type("S", (), {"id": 2, "name": "知行岛自习室(理工大店)"})(),
    ]
    hit = infer_store_from_deal_name(stores, "千峰店团购两小时")
    assert hit.id == 1


def test_deal_name_without_store_is_not_inferred():
    from app.services.exchange_setting import infer_store_from_deal_name

    stores = [
        type("S", (), {"id": 1, "name": "知行岛自习室(千峰南路店)"})(),
        type("S", (), {"id": 2, "name": "知行岛自习室(理工大店)"})(),
    ]
    assert infer_store_from_deal_name(stores, "【新客体验】自习室2小时") is None


def test_deal_name_matching_both_is_not_inferred():
    from app.services.exchange_setting import infer_store_from_deal_name

    stores = [
        type("S", (), {"id": 1, "name": "知行岛自习室(千峰南路店)"})(),
        type("S", (), {"id": 2, "name": "知行岛自习室(理工大店)"})(),
    ]
    assert infer_store_from_deal_name(stores, "千峰理工大通用四小时") is None


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
    test_deal_name_picks_ligongda()
    test_deal_name_picks_qianfeng_short()
    test_deal_name_without_store_is_not_inferred()
    test_deal_name_matching_both_is_not_inferred()
    test_no_open_store()
    print("ok")
