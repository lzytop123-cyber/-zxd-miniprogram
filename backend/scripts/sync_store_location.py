"""将门店 #1 同步为高德认证地址与坐标（可重复执行）。"""

from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Store

# 高德「知行岛·自习室」认证信息；坐标请在 lbs.amap.com/tools/picker 点 B604 门洞微调后改这里
VERIFIED_STORE = {
    "name": "知行岛·自习室",
    "address": "太原市万柏林区融创长风壹号3号公寓2单元B604室",
    "latitude": Decimal("37.820712"),
    "longitude": Decimal("112.517856"),
}


def main() -> None:
    db = SessionLocal()
    try:
        store = db.scalar(select(Store).order_by(Store.id).limit(1))
        if not store:
            print("未找到门店，请先运行 seed.py")
            return
        for key, value in VERIFIED_STORE.items():
            setattr(store, key, value)
        db.commit()
        print(f"已更新门店 #{store.id}: {store.name}")
        print(f"  地址: {store.address}")
        print(f"  坐标: {store.latitude}, {store.longitude}")
        print("若导航仍有偏差，请在高德坐标拾取器点门洞后改 scripts/sync_store_location.py 再运行本脚本")
    finally:
        db.close()


if __name__ == "__main__":
    main()
