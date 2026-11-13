"""各门店独立座位图：草稿/发布/可订座位。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db.session import Base  # noqa: E402
from app.models import Seat, Store, StoreSeatMap, Zone  # noqa: E402
from app.services.schema_migrate import run_schema_migrations  # noqa: E402
from app.services.seat_setup import ensure_store_seats  # noqa: E402
from app.services.store_seat_maps import (  # noqa: E402
    SeatMapError,
    get_published_map,
    list_bookable_seats,
    publish_draft_map,
    restore_map,
    save_draft_map,
)


engine = create_engine("sqlite://")
SessionLocal = sessionmaker(bind=engine)


class StoreSeatMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            run_schema_migrations(db)
            db.commit()
        finally:
            db.close()

        temp = TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        upload_root = Path(temp.name)
        upload_patch = patch("app.services.store_seat_maps.UPLOADS_DIR", upload_root)
        upload_patch.start()
        cls.addClassCleanup(upload_patch.stop)
        uploads = upload_root / "seat-maps"
        uploads.mkdir(parents=True, exist_ok=True)
        cls._img = uploads / "test_map.png"
        cls._img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
        cls._img_path = "/static/seat-maps/test_map.png"

    def setUp(self):
        self.db = SessionLocal()
        self._cleanup()

    def tearDown(self):
        self._cleanup()
        self.db.close()

    def _cleanup(self):
        for model in (StoreSeatMap, Seat, Zone, Store):
            for row in self.db.scalars(select(model)).all():
                self.db.delete(row)
        self.db.commit()

    def _legacy_store(self) -> Store:
        s = Store(name="千峰", status=1, seat_map_mode="legacy")
        self.db.add(s)
        self.db.flush()
        ensure_store_seats(self.db, s)
        self.db.commit()
        self.db.refresh(s)
        return s

    def _image_store(self) -> Store:
        s = Store(name="理工大", status=1, seat_map_mode="image")
        self.db.add(s)
        self.db.flush()
        z = Zone(store_id=s.id, name="A区", type="standard", sort_order=0)
        self.db.add(z)
        self.db.flush()
        for code in ("A1", "A2", "A3"):
            self.db.add(
                Seat(
                    store_id=s.id,
                    zone_id=z.id,
                    seat_code=code,
                    seat_type="standard",
                    status=1,
                )
            )
        self.db.commit()
        self.db.refresh(s)
        return s

    def test_legacy_default_and_ensure(self):
        store = self._legacy_store()
        self.assertEqual(store.seat_map_mode, "legacy")
        seats = list_bookable_seats(self.db, store)
        self.assertEqual(len(seats), 28)

    def test_image_unpublished_not_bookable(self):
        store = self._image_store()
        self.assertEqual(list_bookable_seats(self.db, store), [])

    def test_draft_does_not_publish(self):
        store = self._image_store()
        seats = list(self.db.scalars(select(Seat).where(Seat.store_id == store.id)).all())
        markers = [
            {"seat_id": seats[0].id, "x_pct": 10, "y_pct": 20, "orient": "up"},
            {"seat_id": seats[1].id, "x_pct": 30, "y_pct": 40, "orient": "up"},
        ]
        save_draft_map(
            self.db,
            store.id,
            image_path=self._img_path,
            aspect_ratio=1.5,
            markers=markers,
        )
        self.db.commit()
        self.assertIsNone(get_published_map(self.db, store.id))
        self.assertIsNone(store.floor_plan)
        self.assertEqual(list_bookable_seats(self.db, store), [])

    def test_publish_switches_bookable(self):
        store = self._image_store()
        seats = list(self.db.scalars(select(Seat).where(Seat.store_id == store.id)).all())
        markers = [
            {"seat_id": seats[0].id, "x_pct": 10, "y_pct": 20, "orient": "up"},
            {"seat_id": seats[1].id, "x_pct": 30, "y_pct": 40, "orient": "up"},
        ]
        save_draft_map(
            self.db,
            store.id,
            image_path=self._img_path,
            aspect_ratio=1.5,
            markers=markers,
        )
        with self.assertRaisesRegex(SeatMapError, "A3"):
            publish_draft_map(self.db, store.id, require_all_enabled=True)
        self.assertIsNone(get_published_map(self.db, store.id))
        seats[2].status = 0
        self.db.flush()
        published = publish_draft_map(self.db, store.id, require_all_enabled=True)
        self.db.commit()
        self.db.refresh(store)
        self.assertEqual(published.state, "published")
        self.assertEqual(store.floor_plan, self._img_path)
        bookable = list_bookable_seats(self.db, store)
        self.assertEqual({s.id for s in bookable}, {seats[0].id, seats[1].id})

    def test_reject_cross_store_marker(self):
        a = self._image_store()
        b = self._image_store()
        foreign = self.db.scalar(select(Seat).where(Seat.store_id == b.id))
        with self.assertRaises(SeatMapError):
            save_draft_map(
                self.db,
                a.id,
                image_path=self._img_path,
                aspect_ratio=1.2,
                markers=[{"seat_id": foreign.id, "x_pct": 1, "y_pct": 1, "orient": "up"}],
            )

    def test_live_board_includes_published_seat_numbers_above_28(self):
        from types import SimpleNamespace
        from app.api.routes.admin_tools import store_live_board

        store = self._image_store()
        seat = self.db.scalar(select(Seat).where(Seat.store_id == store.id))
        seat.seat_code = "35"
        save_draft_map(
            self.db, store.id, image_path=self._img_path, aspect_ratio=1.2,
            markers=[{"seat_id": seat.id, "x_pct": 91, "y_pct": 72, "orient": "up"}],
        )
        publish_draft_map(self.db, store.id)
        self.db.commit()

        response = store_live_board(store.id, SimpleNamespace(role="store", store_id=store.id), self.db)
        self.assertEqual(response.data["store_name"], store.name)
        self.assertEqual(response.data["counts"]["free"], 1)
        item, = response.data["seats"]
        self.assertEqual((item["seat_code"], item["left_pct"], item["top_pct"]), ("35", 91, 72))

    def test_ensure_noop_for_image(self):
        store = self._image_store()
        before = self.db.scalars(select(Seat).where(Seat.store_id == store.id)).all()
        added = ensure_store_seats(self.db, store)
        self.db.commit()
        after = self.db.scalars(select(Seat).where(Seat.store_id == store.id)).all()
        self.assertEqual(added, 0)
        self.assertEqual(len(before), len(after))

    def test_restore_archived(self):
        store = self._image_store()
        seats = list(self.db.scalars(select(Seat).where(Seat.store_id == store.id)).all())
        save_draft_map(
            self.db,
            store.id,
            image_path=self._img_path,
            aspect_ratio=1.5,
            markers=[{"seat_id": seats[0].id, "x_pct": 10, "y_pct": 10, "orient": "up"}],
        )
        v1 = publish_draft_map(self.db, store.id)
        self.db.commit()
        save_draft_map(
            self.db,
            store.id,
            image_path=self._img_path,
            aspect_ratio=1.5,
            markers=[
                {"seat_id": seats[0].id, "x_pct": 10, "y_pct": 10, "orient": "up"},
                {"seat_id": seats[1].id, "x_pct": 20, "y_pct": 20, "orient": "up"},
            ],
        )
        publish_draft_map(self.db, store.id)
        self.db.commit()
        self.db.refresh(v1)
        self.assertEqual(v1.state, "archived")
        restored = restore_map(self.db, store.id, v1.id)
        self.db.commit()
        self.assertEqual(restored.state, "published")
        self.assertEqual(len(restored.markers or []), 1)


if __name__ == "__main__":
    unittest.main()
