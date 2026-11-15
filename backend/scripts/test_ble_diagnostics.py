from types import SimpleNamespace
from fastapi import HTTPException
from app.api.routes.ble import DoorLogRequest, report_door_log
from app.models import Reservation

class DB:
    def __init__(self):
        self.logs = []
        self.values = iter([None, 9])
    def scalar(self, query):
        return next(self.values)
    def get(self, model, key):
        assert model is Reservation
        return SimpleNamespace(id=1, user_id=2, store_id=3)
    def add(self, obj):
        self.logs.append(obj)
    def commit(self):
        pass

db = DB()
report_door_log(1, DoorLogRequest(reservation_id=1, result='fail', error_msg='permission denied',
    error_code='10001', stage='adapter', duration_ms=240, client_system='Android', plugin_version='3.1.4'),
    user=SimpleNamespace(id=2), db=db)
assert len(db.logs) == 1
assert db.logs[0].lock_id == 9
assert '10001' in db.logs[0].fail_reason and 'adapter' in db.logs[0].fail_reason
assert len(db.logs[0].fail_reason) <= 200
try:
    report_door_log(1, DoorLogRequest(reservation_id=1, result='fail'), user=SimpleNamespace(id=99), db=DB())
    raise AssertionError('Foreign reservation accepted')
except HTTPException as exc:
    assert exc.status_code == 404
print('BLE diagnostics: missing-key failure logging and ownership checks passed')
