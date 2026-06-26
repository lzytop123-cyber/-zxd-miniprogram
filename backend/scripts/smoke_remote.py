"""对线上 API 做冒烟测试。用法:

  set ZXD_API_BASE=https://api.example.com
  set ZXD_ADMIN_PASSWORD=你的后台密码
  python scripts/smoke_remote.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASE = os.environ.get("ZXD_API_BASE", "").rstrip("/")
ADMIN_PASSWORD = os.environ.get("ZXD_ADMIN_PASSWORD", "admin123")
ADMIN_USER = os.environ.get("ZXD_ADMIN_USERNAME", "admin")


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    raise SystemExit(1)


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


def api_ok(name: str, r: httpx.Response):
    try:
        data = r.json()
    except Exception:
        fail(f"{name}: HTTP {r.status_code} {r.text[:200]}")
    if data.get("code") != 0:
        fail(f"{name}: {data}")
    ok(name)
    return data.get("data")


def main() -> None:
    if not BASE:
        fail("请设置环境变量 ZXD_API_BASE，例如 https://api.example.com")

    print(f"Testing {BASE}\n")
    c = httpx.Client(base_url=BASE, timeout=20, trust_env=False)

    r = c.get("/health")
    if r.status_code != 200 or r.json().get("status") != "ok":
        fail(f"health: {r.status_code} {r.text[:200]}")
    ok("health")

    user = api_ok("user login (PRE_WECHAT dev)", c.post("/api/user/login", json={"code": "smoke_remote_test"}))
    h = {"Authorization": f"Bearer {user['token']}"}

    stores = api_ok("store list", c.get("/api/store/list"))
    if not stores:
        fail("store list empty")
    store_id = stores[0]["id"]

    seats = api_ok("store seats", c.get(f"/api/store/{store_id}/seats"))
    if len(seats) < 1:
        fail("no seats")

    api_ok("user profile", c.get("/api/user/profile", headers=h))
    api_ok("user cards", c.get("/api/user/cards", headers=h))

    admin = api_ok(
        "admin login",
        c.post("/api/admin/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD}),
    )
    ah = {"Authorization": f"Bearer {admin['token']}"}
    api_ok("admin stats", c.get("/api/admin/stats", headers=ah))
    admin_seats = api_ok("admin seats", c.get("/api/admin/seats", params={"store_id": store_id}, headers=ah))
    api_ok("admin deal mappings", c.get("/api/admin/deal-mappings", headers=ah))

    print(f"\nAll passed. seats={len(seats)}, admin_seats={len(admin_seats)}")
    print("Next: miniprogram config.js → PROD_API_BASE, then test Meituan exchange in app.")


if __name__ == "__main__":
    main()
