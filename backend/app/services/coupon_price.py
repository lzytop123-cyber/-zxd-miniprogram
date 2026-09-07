"""团购核销金额：从云老板/抖音回包解析返回价（元）。"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation


def _to_yuan(raw, *, as_fen: bool = False) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        val = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        return None
    if val < 0:
        return None
    if as_fen:
        val = val / Decimal(100)
    return val.quantize(Decimal("0.01"))


def _price_from_amount_block(amount: dict | None) -> Decimal | None:
    """抖音 amount（分）。跳过 0，避免 coupon_pay_amount=0 盖住真实 pay_amount。"""
    if not isinstance(amount, dict):
        return None
    for key in (
        "pay_amount",
        "coupon_pay_amount",
        "original_amount",
        "list_market_amount",
    ):
        yuan = _to_yuan(amount.get(key), as_fen=True)
        if yuan is not None and yuan > 0:
            return yuan
    return None


def _price_from_douyin_cert(cert: dict) -> Decimal | None:
    yuan = _price_from_amount_block(cert.get("amount") if isinstance(cert.get("amount"), dict) else None)
    if yuan is not None:
        return yuan

    time_card = cert.get("time_card") if isinstance(cert.get("time_card"), dict) else {}
    serials = time_card.get("serial_amount_list") or []
    if isinstance(serials, list):
        for item in serials:
            if not isinstance(item, dict):
                continue
            yuan = _price_from_amount_block(item.get("amount") if isinstance(item.get("amount"), dict) else None)
            if yuan is not None:
                return yuan

    sku = cert.get("sku") if isinstance(cert.get("sku"), dict) else {}
    for key in ("market_price", "actual_amount", "origin_amount", "price"):
        yuan = _to_yuan(sku.get(key), as_fen=True)
        if yuan is not None and yuan > 0:
            return yuan
    return None


def _unwrap_douyin_payload(raw: dict | None) -> dict | None:
    if not isinstance(raw, dict):
        return None
    if "raw_prepare" in raw and isinstance(raw["raw_prepare"], dict):
        raw = raw["raw_prepare"]
    if "certificates" not in raw and "certificates_v2" not in raw and "certificate" not in raw:
        data = raw.get("data")
        if isinstance(data, dict):
            raw = data
    return raw if isinstance(raw, dict) else None


def _price_from_verify_blob(blob) -> Decimal | None:
    """解析核销 result（dict 或 JSON 字符串）。"""
    data = blob
    if isinstance(blob, str):
        text = blob.strip()
        if not text or text[0] not in "{[":
            return None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None

    for path in (
        ("verify_result",),
        ("verify_result", "certificate"),
        ("raw_verify",),
        ("data",),
    ):
        cur: object = data
        ok = True
        for key in path:
            if not isinstance(cur, dict) or key not in cur:
                ok = False
                break
            cur = cur[key]
        if not ok or not isinstance(cur, dict):
            continue
        if "amount" in cur or "sku" in cur:
            yuan = _price_from_douyin_cert(cur)
            if yuan is not None:
                return yuan
        cert = cur.get("certificate")
        if isinstance(cert, dict):
            yuan = _price_from_douyin_cert(cert)
            if yuan is not None:
                return yuan
        certs = cur.get("certificates_v2") or cur.get("certificates") or []
        if certs and isinstance(certs[0], dict):
            yuan = _price_from_douyin_cert(certs[0])
            if yuan is not None:
                return yuan
    return None


def extract_deal_price(
    *,
    ticket_data: dict | None = None,
    prepared: dict | None = None,
    douyin_raw: dict | None = None,
    meituan_raw: dict | None = None,
    consume_result: str | dict | None = None,
) -> Decimal | None:
    """优先 dealPrice（元），其次 payAmount（分），再抖音 certificate.amount / 核销回包。"""
    if prepared and prepared.get("deal_price") is not None:
        yuan = _to_yuan(prepared.get("deal_price"), as_fen=False)
        if yuan is not None and yuan > 0:
            return yuan
    if douyin_raw and douyin_raw.get("deal_price") is not None:
        yuan = _to_yuan(douyin_raw.get("deal_price"), as_fen=False)
        if yuan is not None and yuan > 0:
            return yuan

    td = ticket_data
    if td is None and prepared:
        td = prepared.get("ticketData") if isinstance(prepared.get("ticketData"), dict) else None
    if td is None and meituan_raw and isinstance(meituan_raw.get("ticketData"), dict):
        td = meituan_raw["ticketData"]
    td = td or {}

    # ticketData 内嵌的抖音 amount
    yuan = _price_from_amount_block(td.get("amount") if isinstance(td.get("amount"), dict) else None)
    if yuan is not None:
        return yuan

    for key in ("dealPrice", "deal_price", "price"):
        yuan = _to_yuan(td.get(key), as_fen=False)
        if yuan is not None and yuan > 0:
            return yuan

    pay = None
    if prepared:
        pay = prepared.get("payAmount")
    if pay is None and meituan_raw:
        pay = meituan_raw.get("payAmount")
    yuan = _to_yuan(pay, as_fen=True)
    if yuan is not None and yuan > 0:
        return yuan

    for candidate in (douyin_raw, prepared, meituan_raw):
        payload = _unwrap_douyin_payload(candidate if isinstance(candidate, dict) else None)
        if not payload:
            continue
        if isinstance(payload.get("certificate"), dict):
            yuan = _price_from_douyin_cert(payload["certificate"])
            if yuan is not None:
                return yuan
        certs = payload.get("certificates_v2") or payload.get("certificates") or []
        if certs and isinstance(certs[0], dict):
            yuan = _price_from_douyin_cert(certs[0])
            if yuan is not None:
                return yuan

    # 核销 result / 历史 meituan_raw.result
    for blob in (
        consume_result,
        (meituan_raw or {}).get("result") if isinstance(meituan_raw, dict) else None,
    ):
        yuan = _price_from_verify_blob(blob)
        if yuan is not None:
            return yuan

    return None
