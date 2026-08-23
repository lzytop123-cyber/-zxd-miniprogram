"""错题本本地回归：列表 / 上传 / 手填保存 / 状态。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models import User
from app.services.schema_migrate import run_schema_migrations

JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00"
    + bytes([8] * 64)
    + b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
    b"\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08"
    b"\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\x7f\x00\xff\xd9"
)

PRESET = ["政治", "英语", "数学", "行测", "申论", "专业课", "其他"]


def _headers(user_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(f'user:{user_id}')}"}


def main() -> int:
    db = SessionLocal()
    try:
        run_schema_migrations(db)
        user = db.scalar(select(User).order_by(User.id.asc()))
        if not user:
            user = User(openid="wb_verify_tmp", nickname="wb-verify")
            db.add(user)
            db.commit()
            db.refresh(user)
        print("user", user.id)

        client = TestClient(app)
        headers = _headers(user.id)

        noauth = client.get("/api/wrongbook/subjects")
        assert noauth.status_code == 401, noauth.text
        print("[OK] 401 without token")

        subs = client.get("/api/wrongbook/subjects", headers=headers)
        assert subs.status_code == 200, subs.text
        names = [s["name"] for s in subs.json()["data"]]
        assert set(PRESET).issubset(set(names)), names
        print("[OK] subjects seeded", names[:7])
        sid = subs.json()["data"][0]["id"]

        up = client.post(
            "/api/wrongbook/upload",
            headers=headers,
            files={"file": ("q.jpg", JPEG, "image/jpeg")},
            data={"type": "question"},
        )
        assert up.status_code == 200, up.text
        udata = up.json()["data"]
        assert udata["url"].startswith("/static/wrongbook/"), udata
        assert udata.get("ocr_text") == ""
        print("[OK] upload", udata["url"], "ocr_empty")

        created = client.post(
            "/api/wrongbook",
            headers=headers,
            json={
                "subject_id": sid,
                "image_urls": [udata["url"]],
                "ocr_text": "手填题干：1+1=?",
                "answer_text": "2",
                "answer_image_urls": [],
                "reason": "计算失误",
                "tags": ["基础", "计算"],
            },
        )
        assert created.status_code == 200, created.text
        qid = created.json()["data"]["id"]
        assert created.json()["data"]["ocr_text"] == "手填题干：1+1=?"
        print("[OK] create question", qid)

        lst = client.get(f"/api/wrongbook/list?subject_id={sid}&keyword=手填", headers=headers)
        assert lst.status_code == 200, lst.text
        items = lst.json()["data"]["items"]
        assert any(i["id"] == qid for i in items), items
        print("[OK] list filter", lst.json()["data"]["total"])

        detail = client.get(f"/api/wrongbook/{qid}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["data"]["status"] == 0
        print("[OK] detail")

        st = client.put(
            f"/api/wrongbook/{qid}",
            headers=headers,
            json={"status": 1, "bump_review": True},
        )
        assert st.status_code == 200, st.text
        assert st.json()["data"]["status"] == 1
        assert st.json()["data"]["review_count"] >= 1
        print("[OK] status+review", st.json()["data"]["status_label"], st.json()["data"]["review_count"])

        tags = client.get("/api/wrongbook/tags", headers=headers)
        assert "基础" in tags.json()["data"]
        print("[OK] tags", tags.json()["data"][:5])

        blocked = client.delete(f"/api/wrongbook/subjects/{sid}", headers=headers)
        assert blocked.status_code == 400
        assert "请先移动或删除" in blocked.json()["detail"]
        print("[OK] delete subject blocked")

        custom = client.post("/api/wrongbook/subjects", headers=headers, json={"name": "验证券科"})
        assert custom.status_code == 200, custom.text
        cid = custom.json()["data"]["id"]
        deleted_q = client.delete(f"/api/wrongbook/{qid}", headers=headers)
        assert deleted_q.status_code == 200, deleted_q.text
        gone = client.delete(f"/api/wrongbook/subjects/{cid}", headers=headers)
        assert gone.status_code == 200, gone.text
        print("[OK] custom subject add/delete")

        upload_path = ROOT / "uploads" / "wrongbook" / Path(udata["url"]).name
        if upload_path.exists():
            upload_path.unlink()
            print("[OK] cleaned upload", upload_path.name)

        print("ALL PASSED")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
