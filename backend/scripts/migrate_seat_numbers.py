"""将门店座位编号统一迁移为平面图 1–27 号。"""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Store
from app.services.seat_setup import migrate_store_seat_codes


def main() -> None:
    db = SessionLocal()
    try:
        stores = db.scalars(select(Store).where(Store.status == 1)).all()
        total_renamed = 0
        total_added = 0
        for store in stores:
            result = migrate_store_seat_codes(db, store)
            db.commit()
            total_renamed += result["renamed"]
            total_added += result["added"]
            print(
                f"store #{store.id} {store.name!r}: "
                f"renamed {result['renamed']}, added {result['added']}"
            )
        print(f"done, renamed {total_renamed}, added {total_added}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
