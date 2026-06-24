"""Sprint 3/4 API smoke test: exchange, period card, points, seats."""

import httpx
from datetime import datetime, timedelta

BASE = "http://127.0.0.1:8000"


def ok(name: str, r: httpx.Response):
    data = r.json()
    assert data.get("code") == 0, f"{name} failed: {data}"
    print(f"[OK] {name}")
    return data.get("data")


def main():
    c = httpx.Client(trust_env=False, base_url=BASE, timeout=20)

    user = ok("login", c.post("/api/user/login", json={"code": "sprint4_test"}))
    h = {"Authorization": f"Bearer {user['token']}"}

    stores = ok("store list", c.get("/api/store/list"))
    store_id = stores[0]["id"]
    seats = ok("store seats", c.get(f"/api/store/{store_id}/seats"))
    assert len(seats) >= 24, f"expected >=24 seats, got {len(seats)}"

    ok("exchange meituan", c.post("/api/exchange/meituan/8888001", headers=h))
    cards = ok("user cards", c.get("/api/user/cards", headers=h))
    assert cards, "no period cards after exchange"

    ok("exchange records", c.get("/api/exchange/records", headers=h))
    ok("points logs", c.get("/api/user/points/logs", headers=h))

    profile = ok("profile invite code", c.get("/api/user/profile", headers=h))
    assert profile.get("invite_code"), "missing invite_code"

    start = datetime.now().replace(microsecond=0) + timedelta(days=1)
    end = start + timedelta(hours=2)
    avail = ok(
        "availability",
        c.get(
            f"/api/store/{store_id}/availability",
            params={"start_time": start.isoformat(), "end_time": end.isoformat()},
            headers=h,
        ),
    )
    free = next((s for s in avail if s["status"] == "available"), None)
    assert free, "no available seat"

    admin = ok("admin login", c.post("/api/admin/login", json={"username": "admin", "password": "admin123"}))
    ah = {"Authorization": f"Bearer {admin['token']}"}
    admin_seats = ok("admin seats", c.get("/api/admin/seats", params={"store_id": store_id}, headers=ah))
    assert len(admin_seats) >= 24

    print("Sprint 3/4 API flow: ALL PASSED")


if __name__ == "__main__":
    main()
