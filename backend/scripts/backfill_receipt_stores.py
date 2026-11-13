"""把未写门店的历史核销和收款记到千峰南路（store id 1）。

不覆盖已有 store_id，因此理工大店（store id 2）的订单和收款保持原样。
只填补空值。重复执行不会改已经写上门店的行；若那时又出现未写门店的已核销订单或收款，
这些空值仍会记到千峰南路，建议部署后执行一次。使用当前进程的 DATABASE_URL。

默认只试运行并回滚。核对打印的门店名称和行数后，再加 --apply 写入。

    PYTHONPATH=backend python backend/scripts/backfill_receipt_stores.py
    PYTHONPATH=backend python backend/scripts/backfill_receipt_stores.py --apply
"""
import argparse

from app.db.session import SessionLocal
from app.services.receipt_store_backfill import backfill_receipt_stores


def main() -> None:
    parser = argparse.ArgumentParser(description="回填收款与历史核销的门店归属")
    parser.add_argument("--apply", action="store_true", help="写入数据库；省略时只试运行")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        stats = backfill_receipt_stores(db)
        action = "已写入" if args.apply else "试运行，未写入"
        if args.apply:
            db.commit()
        else:
            db.rollback()
        print(
            f"{action}。门店 #{stats['legacy_store_id']} {stats['legacy_store_name']}："
            f"核销订单补门店 {stats['orders_assigned']}，"
            f"按订单写入收款 {stats['receipts_from_orders']}，"
            f"无订单归属的收款记入该店 {stats['receipts_legacy']}。"
        )
        print("已有门店的订单和收款不会改动。可重复执行。")
        if not args.apply:
            print("确认无误后加 --apply 再执行一次。")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
