"""上线前自检（跳过微信项）。在服务器上: python scripts/deploy_check.py"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402


def ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def warn(msg: str) -> None:
    print(f"  [!!] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def main() -> int:
    errors = 0
    print("知行岛 deploy_check（非微信）\n")

    if settings.secret_key in ("change-me", "change-me-in-production") or len(settings.secret_key) < 32:
        fail("SECRET_KEY 过短或为默认值")
        errors += 1
    else:
        ok("SECRET_KEY 已设置")

    if settings.admin_password in ("admin123", "请设置强密码"):
        fail("ADMIN_PASSWORD 仍为弱密码/占位符")
        errors += 1
    else:
        ok("ADMIN_PASSWORD 已修改")

    if "sqlite" in settings.database_url.lower():
        warn("DATABASE_URL 仍为 SQLite，生产建议 MySQL")
    elif "mysql" in settings.database_url.lower():
        ok(f"DATABASE_URL → MySQL")
    else:
        warn(f"DATABASE_URL: {settings.database_url[:40]}...")

    if settings.coupon_provider == "meituan":
        if settings.yunlaoban_client_id and settings.yunlaoban_secret and settings.yunlaoban_shop_id:
            ok(f"云老板/美团已配置 shop={settings.yunlaoban_shop_id}")
        else:
            fail("COUPON_PROVIDER=meituan 但云老板凭证不完整")
            errors += 1
    else:
        warn(f"COUPON_PROVIDER={settings.coupon_provider}（生产建议 meituan）")

    if settings.pre_wechat_launch:
        ok("PRE_WECHAT_LAUNCH=true（审核期：未配微信时可用 dev 登录 / mock 支付）")
    elif not settings.wx_login_configured:
        warn("未配置微信登录且 PRE_WECHAT_LAUNCH=false，小程序将无法登录")

    if settings.wx_login_configured:
        ok("微信 AppID 已配置")
    else:
        print("  [--] 微信登录：跳过（审核中）")

    if settings.wx_pay_configured:
        cert = Path(settings.wx_pay_key_path)
        if cert.is_file():
            ok("微信支付证书存在")
        else:
            fail(f"已填 WX_PAY_MCHID 但私钥不存在: {cert}")
            errors += 1
    else:
        print("  [--] 微信支付：跳过（审核中）")

    if settings.ttlock_client_id:
        ok("通通锁凭证已填")
    else:
        print("  [--] 通通锁：未配置（可后续补）")

    if settings.base_url.startswith("https://"):
        ok(f"BASE_URL={settings.base_url}")
    elif settings.base_url.startswith("http://"):
        warn(f"BASE_URL={settings.base_url}（备案前可先用 IP/HTTP 测后台与 API）")
    else:
        warn(f"BASE_URL={settings.base_url}")

    print()
    if errors:
        print(f"未通过: {errors} 项需修复")
        return 1
    print("检查完成（微信相关项已按跳过处理）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
