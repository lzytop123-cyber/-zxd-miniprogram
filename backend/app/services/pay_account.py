"""按门店解析微信支付收款账户。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import PayAccount, Store


@dataclass(frozen=True)
class ResolvedPayAccount:
    mchid: str
    source: str  # "default" | "bound"
    serial_no: str = ""
    api_v3_key: str = ""
    cert_path: str = ""
    key_path: str = ""
    public_key_id: str = ""
    public_key_path: str = ""
    account_id: int | None = None

    @property
    def is_bound(self) -> bool:
        return self.source == "bound"


def _account_complete(acc: PayAccount) -> bool:
    return bool(
        (acc.mchid or "").strip()
        and (acc.serial_no or "").strip()
        and (acc.api_v3_key or "").strip()
        and (acc.key_path or "").strip()
    )


def default_pay_account() -> ResolvedPayAccount:
    return ResolvedPayAccount(
        mchid=(settings.wx_pay_mchid or "").strip() or "mock_default",
        source="default",
        serial_no=(settings.wx_pay_serial_no or "").strip(),
        api_v3_key=(settings.wx_pay_api_v3_key or "").strip(),
        cert_path=(settings.wx_pay_cert_path or "").strip(),
        key_path=(settings.wx_pay_key_path or "").strip(),
        public_key_id=(settings.wx_pay_public_key_id or "").strip(),
        public_key_path=(settings.wx_pay_public_key_path or "").strip(),
        account_id=None,
    )


def resolve_pay_account(db: Session, store: Store) -> ResolvedPayAccount:
    """
    门店绑定账户优先；未绑定走全局 .env。
    已绑定但停用/不完整时抛错，禁止回退默认商户。
    """
    if store.pay_account_id:
        acc = db.get(PayAccount, store.pay_account_id)
        if not acc or acc.status != 1:
            raise ValueError("门店收款账户不可用，请联系管理员配置")
        if not _account_complete(acc):
            raise ValueError("门店收款账户配置不完整，无法支付")
        return ResolvedPayAccount(
            mchid=acc.mchid.strip(),
            source="bound",
            serial_no=(acc.serial_no or "").strip(),
            api_v3_key=(acc.api_v3_key or "").strip(),
            cert_path=(acc.cert_path or "").strip(),
            key_path=(acc.key_path or "").strip(),
            public_key_id=(acc.public_key_id or "").strip(),
            public_key_path=(acc.public_key_path or "").strip(),
            account_id=acc.id,
        )
    return default_pay_account()


def list_resolved_accounts_for_notify(db: Session) -> list[ResolvedPayAccount]:
    """回调验签：默认账户 + 所有启用中的收款账户。"""
    accounts = [default_pay_account()]
    seen = {accounts[0].mchid}
    for acc in db.scalars(select(PayAccount).where(PayAccount.status == 1)).all():
        if not _account_complete(acc):
            continue
        mchid = acc.mchid.strip()
        if mchid in seen:
            continue
        seen.add(mchid)
        accounts.append(
            ResolvedPayAccount(
                mchid=mchid,
                source="bound",
                serial_no=(acc.serial_no or "").strip(),
                api_v3_key=(acc.api_v3_key or "").strip(),
                cert_path=(acc.cert_path or "").strip(),
                key_path=(acc.key_path or "").strip(),
                public_key_id=(acc.public_key_id or "").strip(),
                public_key_path=(acc.public_key_path or "").strip(),
                account_id=acc.id,
            )
        )
    return accounts


def assert_store_allows_pay_type(store: Store, pay_type: str) -> None:
    """benefits_isolated 门店禁止余额支付。"""
    if getattr(store, "benefits_isolated", 0) and pay_type == "balance":
        raise ValueError("该门店不支持余额支付，请使用微信支付")


def assert_coupon_allowed_for_store(store: Store, coupon_has_store: bool = False) -> None:
    if getattr(store, "benefits_isolated", 0) and not coupon_has_store:
        raise ValueError("该门店不可使用全局优惠券")
