"""测试抖音官方核销连通性（在服务器或本地执行）。

用法:
  cd backend && python scripts/test_douyin.py [券码]
未传券码时仅测 client_token。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.services.douyin import DouyinService, normalize_coupon_input, use_douyin_official


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

    code = normalize_coupon_input(sys.argv[1]) if len(sys.argv) > 1 else ""
    if not code:
        import httpx

        async with httpx.AsyncClient(timeout=settings.yunlaoban_timeout_sec) as client:
            token = await DouyinService._get_client_token(client)
        print(f"\n[OK] client_token 获取成功: {token[:16]}...")
        print("传券码可测 prepare+verify: python scripts/test_douyin.py 122510658172674")
        return

    try:
        prepared, verified = await DouyinService.prepare_and_verify(code)
        print("\n[OK] 核销成功")
        print(f"  商品: {prepared.get('ticketName')}")
        print(f"  dealId: {(prepared.get('ticketData') or {}).get('dealId')}")
        print(f"  结果: {verified[:200]}...")
    except Exception as e:
        print(f"\n[FAIL] {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
