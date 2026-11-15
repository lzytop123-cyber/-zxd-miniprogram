from fastapi import HTTPException
from app.models import Store, StoreContactSetting
from app.services.admin_access import scope_store_id


def contact_for_admin(db, admin, store_id):
    sid = scope_store_id(admin, store_id)
    if not sid:
        raise HTTPException(400, "请选择门店")
    if not db.get(Store, sid):
        raise HTTPException(404, "门店不存在")
    row = db.get(StoreContactSetting, sid)
    if row is None:
        row = StoreContactSetting(store_id=sid)
        db.add(row)
        db.flush()
    return row
