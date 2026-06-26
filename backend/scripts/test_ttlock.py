"""测试通通锁开放平台凭证。用法:

  cd backend
  set PYTHONPATH=.
  python scripts/test_ttlock.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.services.business import TTLockService


async def check_network() -> None:
    print("--- 网络自检 ---")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://cnapi.ttlock.com")
        print(f"[OK] 可访问 cnapi.ttlock.com (HTTP {resp.status_code})")
    except httpx.ConnectError as e:
        print(f"[FAIL] HTTPS 连接失败: {e}")
        print("  常见原因: Windows 证书吊销检查失败 (CRYPT_E_REVOCATION_OFFLINE)")
        print("  处理: 确认系统时间正确、能上网；或在 PowerShell 用:")
        print('  curl.exe --ssl-no-revoke -X POST "https://cnapi.ttlock.com/oauth2/token" ...')
        raise SystemExit(1) from e


async def main() -> None:
    if not settings.ttlock_client_id:
        print("[FAIL] 未配置 TTLOCK_CLIENT_ID，请在 backend/.env 填写")
        raise SystemExit(1)

    print(f"clientId: {settings.ttlock_client_id[:8]}...")
    print(f"username: {settings.ttlock_username}")

    await check_network()

    try:
        token = await TTLockService.get_access_token()
        print(f"[OK] access_token: {token[:12]}...")
    except ValueError as e:
        print(f"[FAIL] 获取 token: {e}")
        if "10007" in str(e) or "password" in str(e).lower():
            print("  → 账号或密码错误。请确认:")
            print("    1. TTLOCK_USERNAME = 通通锁 APP 登录手机号")
            print("    2. TTLOCK_PASSWORD = APP 登录密码明文（不是 MD5）")
            print("    3. open.sciener.com 创建应用时用的也是同一账号")
            print("    4. 先在通通锁 APP 用该手机号+密码能正常登录")
        raise SystemExit(1) from e
    except Exception as e:
        print(f"[FAIL] 获取 token: {type(e).__name__}: {e}")
        raise SystemExit(1) from e

    lock_id = input("输入要测试的 lockId（回车跳过远程开锁测试）: ").strip()
    if lock_id:
        try:
            ekey = await TTLockService.get_ekey(lock_id)
            print(f"[OK] lockData 长度: {len(ekey.get('lockData') or '')}")
            print(f"     remoteEnable: {ekey.get('remoteEnable')}")
        except Exception as e:
            print(f"[WARN] get_ekey: {e}")

        ans = input("尝试远程开锁? y/N: ").strip().lower()
        if ans == "y":
            try:
                await TTLockService.remote_unlock(lock_id)
                print("[OK] 远程开锁成功")
            except Exception as e:
                print(f"[FAIL] 远程开锁: {e}")


if __name__ == "__main__":
    asyncio.run(main())
