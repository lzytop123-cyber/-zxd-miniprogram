"""上岸集市基础回归测试（SQLite 开发库）。"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models import MarketListing, MarketListingStatus, Store, User
from app.services.market_seed import ensure_market_categories
from app.services.schema_migrate import run_schema_migrations


def _user_headers(user_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(f'user:{user_id}')}"}


def _admin_headers(admin_id: int = 1) -> dict:
    return {"Authorization": f"Bearer {create_access_token(f'admin:{admin_id}')}"}


def main() -> int:
    db = SessionLocal()
    try:
        run_schema_migrations(db)
        ensure_market_categories(db)

        store = db.scalar(select(Store).where(Store.status == 1))
        if not store:
            print("[FAIL] no store")
            return 1

        user = db.scalar(select(User).order_by(User.id.asc()))
        if not user:
            print("[FAIL] no user — 请先小程序登录一次")
            return 1
        user.phone = user.phone or "13800000000"
        user.market_banned = 0
        db.commit()

        client = TestClient(app)

        meta = client.get("/api/market/meta")
        assert meta.status_code == 200 and meta.json()["data"]["enabled"] is True
        exams = meta.json()["data"]["exam_categories"]
        materials = meta.json()["data"]["material_categories"]
        assert exams and materials
        print("[OK] market meta")

        body = {
            "store_id": store.id,
            "exam_category_id": exams[0]["id"],
            "material_category_id": materials[0]["id"],
            "title": "测试二手考研英语",
            "description": "八成新，仅自测",
            "price": "20.00",
            "images": ["/static/market/test.jpg"],
            "copyright_declared": True,
            "submit": True,
        }
        created = client.post("/api/market/listings", json=body, headers=_user_headers(user.id))
        assert created.status_code == 200, created.text
        listing_id = created.json()["data"]["id"]
        assert created.json()["data"]["status"] == MarketListingStatus.pending.value
        print("[OK] create+submit listing", listing_id)

        pub = client.get(f"/api/market/listings/{listing_id}")
        assert pub.status_code == 404  # 未审核对他人不可见
        print("[OK] unpublished hidden")

        reviewed = client.post(
            f"/api/admin/market/listings/{listing_id}/review",
            json={"approve": True},
            headers=_admin_headers(),
        )
        assert reviewed.status_code == 200, reviewed.text
        assert reviewed.json()["data"]["status"] == "published"
        print("[OK] admin approve")

        detail = client.get(f"/api/market/listings/{listing_id}")
        assert detail.status_code == 200
        assert "reveal" not in str(detail.json()).lower() or "reveal_value" not in detail.text
        print("[OK] published visible")

        fav = client.post(f"/api/market/favorites/{listing_id}", headers=_user_headers(user.id))
        assert fav.status_code == 200
        print("[OK] favorite")

        # 第二个用户联系
        user2 = db.scalar(select(User).where(User.id != user.id).order_by(User.id.asc()))
        if user2:
            user2.phone = user2.phone or "13900000000"
            db.commit()
            contact = client.post(
                "/api/market/contact-requests",
                json={"listing_id": listing_id, "message": "还在吗"},
                headers=_user_headers(user2.id),
            )
            assert contact.status_code == 200, contact.text
            req_id = contact.json()["data"]["id"]
            decide = client.post(
                f"/api/market/contact-requests/{req_id}/decide",
                json={"approve": True, "reveal_type": "phone"},
                headers=_user_headers(user.id),
            )
            assert decide.status_code == 200, decide.text
            reveal = client.get(
                f"/api/market/contact-requests/{req_id}/reveal",
                headers=_user_headers(user2.id),
            )
            assert reveal.status_code == 200
            assert reveal.json()["data"]["reveal_value"]
            # 详情仍无公开联系方式
            d2 = client.get(f"/api/market/listings/{listing_id}")
            assert "13800000000" not in d2.text
            print("[OK] contact approve+reveal")
        else:
            print("[SKIP] contact — need second user")

        print("[PASS] market smoke tests")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
