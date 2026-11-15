"""Run from backend: python -m scripts.test_store_contact (isolated in-memory DB)."""
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import Store, StoreContactSetting, SiteContactSetting
from app.services.store_contact import contact_for_admin
from app.api.routes.home import get_home_contact

engine = create_engine('sqlite://')
for model in (Store, StoreContactSetting, SiteContactSetting):
    model.__table__.create(engine)
with Session(engine) as db:
    db.add_all([Store(id=1, name='A'), Store(id=2, name='B'), SiteContactSetting(id=1, poster_url='/static/legacy.png')])
    db.commit()
    hq = SimpleNamespace(role='hq', store_id=None)
    row = contact_for_admin(db, hq, 1)
    row.poster_url = '/static/a.png'
    db.commit()
    assert get_home_contact(store_id=1, db=db).data['poster_url'].endswith('/static/a.png')
    assert get_home_contact(store_id=2, db=db).data['poster_url'] is None
    try:
        contact_for_admin(db, SimpleNamespace(role='store', store_id=1), 2)
        raise AssertionError('Cross-store access allowed')
    except HTTPException as exc:
        assert exc.status_code == 403
    assert contact_for_admin(db, SimpleNamespace(role='store', store_id=1), None).store_id == 1
print('Store contact isolation checks passed')
