"""测试云老板美团核销连通性（在服务器容器内执行最佳）。

用法:
  python scripts/test_yunlaoban.py
  python scripts/test_yunlaoban.py 1457226281   # 仅检查 deal 映射，不验券
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.services.yunlaoban import YunlaobanService, _use_mock


def main() -> int:
    print("云老板 / 美团核销诊断\n")
    print(f"  COUPON_PROVIDER = {settings.coupon_provider}")
    print(f"  MEITUAN_CLIENT_ID = {'(已配置)' if settings.yunlaoban_client_id else '(空)'}")
    print(f"  MEITUAN_SECRET = {'(已配置)' if settings.yunlaoban_secret else '(空)'}")
    print(f"  MEITUAN_SHOP_ID = {settings.yunlaoban_shop_id or '(空)'}")
    print(f"  use_mock = {_use_mock()}")

    if _use_mock():
        print("\n[!!] 当前走 Mock，不会调用云老板真实核销！")
        print("     请在 backend/.env 填写 MEITUAN_CLIENT_ID / MEITUAN_SECRET / MEITUAN_SHOP_ID")
        print("     并设置 COUPON_PROVIDER=meituan，然后 restart api 容器。")
        return 1

    code = sys.argv[1] if len(sys.argv) > 1 else None
    if not code:
        print("\n凭证已配置。用真实券码测试: python scripts/test_yunlaoban.py <券码>")
        return 0

    async def run():
        try:
            prepared = await YunlaobanService.prepare(1, code)
            deal_id = prepared["ticketData"].get("dealId")
            print(f"\n[OK] prepare 成功")
            print(f"  ticketName = {prepared.get('ticketName')}")
            print(f"  dealId = {deal_id}")
        except ValueError as e:
            print(f"\n[FAIL] prepare: {e}")
            return 1
        return 0

    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
