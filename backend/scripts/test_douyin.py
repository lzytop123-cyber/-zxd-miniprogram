"""测试抖音官方核销连通性（在服务器或本地执行）。

用法:
  cd backend && python scripts/test_douyin.py              # 仅测 token
  cd backend && python scripts/test_douyin.py <券码>       # 只 prepare，不核销（看金额）
  cd backend && python scripts/test_douyin.py <券码> --verify  # prepare+正式核销（慎用）
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.core.config import settings
from app.services.coupon_price import extract_deal_price
from app.services.douyin import DouyinService, normalize_coupon_input, use_douyin_official


def _print_price_fields(prepared: dict) -> None:
    td = prepared.get("ticketData") or {}
    amount = td.get("amount") or {}
    price = extract_deal_price(douyin_raw=prepared.get("raw_prepare"), ticket_data=td)
    print("\n金额字段（官方多为「分」）:")
    if isinstance(amount, dict) and amount:
        for k in (
            "coupon_pay_amount",
            "pay_amount",
            "original_amount",
            "list_market_amount",
            "platform_discount_amount",
            "merchant_ticket_amount",
            "payment_discount_amount",
        ):
            if k in amount:
                print(f"  amount.{k} = {amount.get(k)}")
    else:
        print("  ticketData.amount = (无)")
    print(f"  解析后的返回价(元) = {price}")
    print(f"  ticketData.dealPrice = {td.get('dealPrice')}")


async def main() -> None:
    print("抖音官方核销诊断\n")
    print(f"  DOUYIN_CLIENT_KEY = {'(已配置)' if settings.douyin_client_key else '(空)'}")
    print(f"  DOUYIN_CLIENT_SECRET = {'(已配置)' if settings.douyin_client_secret else '(空)'}")
    print(f"  DOUYIN_POI_ID = {settings.douyin_poi_id or '(空)'}")
    print(f"  DOUYIN_COUPON_PROVIDER = {settings.douyin_coupon_provider or 'auto'}")
    print(f"  走官方 API = {use_douyin_official()}")

    if not use_douyin_official():
        print("\n未启用抖音官方核销：请配置 DOUYIN_CLIENT_KEY/SECRET/POI_ID，并设置 DOUYIN_COUPON_PROVIDER=official")
        sys.exit(1)

    args = [a for a in sys.argv[1:] if a]
    do_verify = "--verify" in args
    code_args = [a for a in args if a != "--verify"]
    code = normalize_coupon_input(code_args[0]) if code_args else ""

    if not code:
        async with httpx.AsyncClient(timeout=settings.yunlaoban_timeout_sec) as client:
            token = await DouyinService._get_client_token(client)
        print(f"\n[OK] client_token 获取成功: {token[:16]}...")
        print("只看价格（不核销）: python scripts/test_douyin.py <券码>")
        print("正式核销（慎用）:   python scripts/test_douyin.py <券码> --verify")
        return

    try:
        async with httpx.AsyncClient(timeout=settings.yunlaoban_timeout_sec) as client:
            prepared = await DouyinService._prepare_with_client(client, code)
        print("\n[OK] prepare 成功（未核销）")
        print(f"  商品: {prepared.get('ticketName')}")
        print(f"  dealId: {(prepared.get('ticketData') or {}).get('dealId')}")
        _print_price_fields(prepared)
        raw = prepared.get("raw_prepare") or {}
        print("\nprepare.data 摘要:")
        print(json.dumps({
            "verify_token": (prepared.get("verify_token") or "")[:16] + "...",
            "order_id": prepared.get("order_id"),
            "certificates_keys": list((raw.get("certificates_v2") or raw.get("certificates") or [{}])[0].keys())
            if (raw.get("certificates_v2") or raw.get("certificates"))
            else [],
        }, ensure_ascii=False, indent=2))

        if do_verify:
            async with httpx.AsyncClient(timeout=settings.yunlaoban_timeout_sec) as client:
                verified = await DouyinService._verify_with_client(client, prepared)
            print("\n[OK] 已正式核销")
            print(f"  结果: {json.dumps(verified, ensure_ascii=False)[:300]}...")
        else:
            print("\n未核销。若要正式核销请加 --verify")
    except Exception as e:
        print(f"\n[FAIL] {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
