"""团购核销金额：从云老板/抖音回包解析返回价（元）。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def _to_yuan(raw, *, fen_hint: bool = False) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        val = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        return None
    if val < 0:
        return None
    if fen_hint:
        # 整数分：990 → 9.90；若已是带小数的元则不再除
        if val == val.to_integral_value() and val >= 1:
            val = val / Decimal(100)
    return val.quantize(Decimal("0.01"))


def extract_deal_price(
    *,
    ticket_data: dict | None = None,
    prepared: dict | None = None,
    douyin_raw: dict | None = None,
    meituan_raw: dict | None = None,
) -> Decimal | None:
    """优先 dealPrice（元），其次 payAmount（通常为分），再尝试抖音 amount。"""
    td = ticket_data
    if td is None and prepared:
        td = prepared.get("ticketData") if isinstance(prepared.get("ticketData"), dict) else None
    if td is None and meituan_raw and isinstance(meituan_raw.get("ticketData"), dict):
        td = meituan_raw["ticketData"]
    td = td or {}

    for key in ("dealPrice", "deal_price", "price"):
        yuan = _to_yuan(td.get(key), fen_hint=False)
        if yuan is not None:
            return yuan

    # 云老板外层 payAmount：分
    pay = None
    if prepared:
        pay = prepared.get("payAmount")
    if pay is None and meituan_raw:
        pay = meituan_raw.get("payAmount")
    yuan = _to_yuan(pay, fen_hint=True)
    if yuan is not None:
        return yuan

    # 抖音官方 prepare 原始结构
    raw = douyin_raw or (prepared or {}).get("raw_prepare")
    if isinstance(raw, dict):
        certs = raw.get("certificates_v2") or raw.get("certificates") or []
        if certs and isinstance(certs[0], dict):
            amount = certs[0].get("amount") or {}
            if isinstance(amount, dict):
                for key in ("pay_amount", "original_amount", "list_market_amount"):
                    yuan = _to_yuan(amount.get(key), fen_hint=True)
                    if yuan is not None:
                        return yuan
            sku = certs[0].get("sku") or {}
            if isinstance(sku, dict):
                for key in ("actual_amount", "origin_amount", "market_price", "price"):
                    # 抖音 sku 金额多为分
                    yuan = _to_yuan(sku.get(key), fen_hint=True)
                    if yuan is not None:
                        return yuan
    return None
