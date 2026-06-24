"""Sprint 1 end-to-end API smoke test."""

import httpx
from datetime import datetime, timedelta

BASE = "http://127.0.0.1:8000"


def ok(name: str, r: httpx.Response):
    data = r.json()
    assert data.get("code") == 0, f"{name} failed: {data}"
    print(f"[OK] {name}")
    return data.get("data")


def main():
    c = httpx.Client(trust_env=False, base_url=BASE, timeout=15)

    assert c.get("/health").json()["status"] == "ok"
    print("[OK] health")

    user = ok("login", c.post("/api/user/login", json={"code": "sprint1_test"}))
    token = user["token"]
    h = {"Authorization": f"Bearer {token}"}

    stores = ok("store list", c.get("/api/store/list"))
    store_id = stores[0]["id"]
    ok("store detail", c.get(f"/api/store/{store_id}"))
    ok("store seats", c.get(f"/api/store/{store_id}/seats"))
    ok("store pricing", c.get(f"/api/store/{store_id}/pricing"))

    start = datetime.now().replace(microsecond=0) + timedelta(hours=1)
    end = start + timedelta(hours=2)
    ok(
        "preview",
        c.post(
            "/api/reservation/preview",
            json={
                "store_id": store_id,
                "bill_type": "hourly",
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
        ),
    )
    created = ok(
        "create",
        c.post(
            "/api/reservation/create",
            json={
                "store_id": store_id,
                "bill_type": "hourly",
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
            headers=h,
        ),
    )
    rid = created["id"]
    order_no = created["order_no"]

    ok("mock pay", c.post(f"/api/reservation/{rid}/mock-pay", headers=h))
    detail = ok("reservation detail", c.get(f"/api/reservation/{rid}", headers=h))
    assert detail["pay_status"] == 1
    active = ok("active reservation", c.get("/api/reservation/active", headers=h))
    assert active is not None

    ble = ok("ble key", c.get(f"/api/ble/key/{rid}", headers=h))
    assert ble.get("lockData")

    ok("checkin", c.post(f"/api/reservation/{rid}/checkin", headers=h))
    ok(
        "door log",
        c.post(
            f"/api/ble/checkin/{rid}",
            json={"reservation_id": rid, "result": "success"},
            headers=h,
        ),
    )

    admin = ok(
        "admin login",
        c.post("/api/admin/login", json={"username": "admin", "password": "admin123"}),
    )
    ah = {"Authorization": f"Bearer {admin['token']}"}
    stats = ok("admin stats", c.get("/api/admin/stats", headers=ah))
    ok("admin orders", c.get("/api/admin/reservations", headers=ah))
    ok("admin locks", c.get("/api/admin/locks", headers=ah))

    print("---")
    print("Sprint 1 API flow: ALL PASSED")
    print(f"order_no={order_no}, seat={created.get('seat_code')}, revenue_today={stats.get('today_revenue')}")


if __name__ == "__main__":
    main()
