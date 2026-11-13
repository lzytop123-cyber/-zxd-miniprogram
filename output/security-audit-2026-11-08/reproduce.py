"""Read-only audit reproductions. Assertions describe CURRENT UNSAFE behavior.
Only synthetic in-memory SQLite data. External payment/TTLock calls are mocked.
Run: backend/.venv/Scripts/python.exe output/security-audit-2026-11-08/reproduce.py
"""
import os
import sys
from pathlib import Path
os.environ.update(APP_ENV="development", DATABASE_URL="sqlite://")
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
import asyncio
import unittest
from datetime import datetime, timedelta, time
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch, AsyncMock
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.session import Base, get_db
from app.models import (User, Store, Zone, Seat, PricingRule, BillType, PayType,
    Reservation, Coupon, BleLock, DoorLog, OpenType, AdminUser, PeriodCard,
    CardType, RechargeOrder, WalletLog, BleKey, StoreCalendarDay, MeituanOrder, MeituanOrderStatus)
from app.models.receipts import Receipt
from app.api.routes import reservation, payment, ble, admin, admin_receipts
from app.api.admin_role_guard import AdminRoleGuardMiddleware
from app.core.security import create_access_token
from app.core import redis_client
from app.services.booking import fulfill_recharge_order
from app.schemas.reservation import ReservationCreateRequest, ReservationPayRequest

class AuditReproductions(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread":False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.S = sessionmaker(bind=self.engine, autoflush=False)
        self.db = self.S()
        self.redis_patch = patch.object(redis_client, "_redis_client", redis_client.MemoryRedis())
        self.redis_patch.start()
        self.start = (datetime.now()+timedelta(days=1)).replace(hour=10,minute=0,second=0,microsecond=0)
        self.user = User(openid="audit-only", nickname="Synthetic", balance=Decimal("1000"), phone="13800000000")
        self.db.add(self.user)
        self.stores = [Store(name="Audit A", status=1), Store(name="Audit B", status=1)]
        self.db.add_all(self.stores)
        self.db.flush()
        self.seats=[]
        for s in self.stores:
            z = Zone(store_id=s.id, name="Synthetic")
            self.db.add(z)
            self.db.flush()
            seat = Seat(store_id=s.id, zone_id=z.id, seat_code="1", status=1)
            self.seats.append(seat)
            self.db.add(seat)
            self.db.add(PricingRule(store_id=s.id, bill_type=BillType.hourly, price=Decimal("10")))
        self.db.commit()
        self.uid=self.user.id

    def tearDown(self):
        self.db.close()
        self.redis_patch.stop()
        self.engine.dispose()

    def make_order(self, store_index=0, coupon_id=None, bill_type=BillType.hourly, end=None):
        return reservation.create(ReservationCreateRequest(
            store_id=self.stores[store_index].id, seat_id=self.seats[store_index].id,
            bill_type=bill_type, start_time=self.start,
            end_time=end or self.start+timedelta(hours=1), coupon_id=coupon_id
        ), self.user, self.db).data

    def balance_pay(self, order_no, db=None, user=None):
        with patch.object(reservation, "finalize_reservation_after_pay", new=AsyncMock()):
            return asyncio.run(reservation.pay(ReservationPayRequest(order_no=order_no,pay_type=PayType.balance),user or self.user,db or self.db))

    def test_01_foreign_door_logs_leak_via_lock_id_http(self):
        locks=[BleLock(store_id=s.id,lock_name="Synthetic",lock_id="audit-lock-"+str(s.id)) for s in self.stores]
        actor=AdminUser(username="audit-store",password_hash="not-used",role="store",store_id=self.stores[0].id,status=1)
        self.db.add_all(locks+[actor]); self.db.flush()
        self.db.add(DoorLog(lock_id=locks[1].id,user_id=self.uid,open_type=OpenType.ble,result=1)); self.db.commit()
        token=create_access_token("admin:"+str(actor.id))
        foreign_lock=locks[1].id
        app=FastAPI(); app.include_router(ble.router,prefix="/api"); app.add_middleware(AdminRoleGuardMiddleware)
        def override_db():
            with self.S() as d: yield d
        app.dependency_overrides[get_db]=override_db
        with patch("app.api.admin_role_guard.SessionLocal",self.S):
            c=TestClient(app); headers={"Authorization":"Bearer "+token}
            normal=c.get("/api/admin/door-logs",headers=headers)
            leaked=c.get("/api/admin/door-logs",params={"lock_id":foreign_lock},headers=headers)
            self.assertEqual(normal.json()["data"]["total"],0)
            self.assertEqual(leaked.status_code,200)
            self.assertEqual(leaked.json()["data"]["items"][0]["user_phone"],"13800000000")

    def test_02_user_refund_failure_marked_refunded(self):
        item=self.make_order(); r=self.db.get(Reservation,item.id)
        r.pay_type=PayType.wechat; r.pay_status=1; self.db.commit()
        with patch.object(reservation.WechatPayService,"refund",return_value=False) as ref:
            reservation.cancel(r.id,self.user,self.db)
        self.assertTrue(ref.called); self.db.refresh(r)
        self.assertEqual((r.status,r.pay_status),(3,2))
        self.assertIsNotNone(r.refunded_at)

    def test_03_admin_refund_failure_marked_refunded(self):
        item=self.make_order(); r=self.db.get(Reservation,item.id)
        r.pay_type=PayType.wechat; r.pay_status=1; self.db.commit()
        with patch.object(admin.WechatPayService,"refund",return_value=False):
            admin.admin_cancel_reservation(r.id,SimpleNamespace(role="hq"),self.db)
        self.db.refresh(r); self.assertEqual((r.status,r.pay_status),(3,2))

    def test_04_one_coupon_discounts_two_orders_without_consumption(self):
        coupon=Coupon(user_id=self.uid,discount_type="amount",discount_val=Decimal("5"),status=0)
        self.db.add(coupon); self.db.commit()
        a=self.make_order(0,coupon.id); b=self.make_order(1,coupon.id)
        self.balance_pay(a.order_no); self.balance_pay(b.order_no)
        self.db.refresh(self.user); self.db.refresh(coupon)
        self.assertEqual(self.user.balance,Decimal("990"))
        self.assertEqual(coupon.status,0)
        self.assertEqual((a.final_price,b.final_price),(Decimal("5"),Decimal("5")))

    def test_05_isolated_store_accepts_discount_if_coupon_omitted_at_pay(self):
        self.stores[1].benefits_isolated=1
        coupon=Coupon(user_id=self.uid,discount_type="amount",discount_val=Decimal("5"),status=0)
        self.db.add(coupon); self.db.commit()
        item=self.make_order(1,coupon.id)
        with patch.object(reservation.WechatPayService,"create_jsapi_order",return_value={"timeStamp":"1","nonceStr":"x","package":"prepay_id=audit","paySign":"x"}) as create:
            asyncio.run(reservation.pay(ReservationPayRequest(order_no=item.order_no,pay_type=PayType.wechat),self.user,self.db))
            self.assertEqual(create.call_args.args[1],Decimal("5"))
        self.db.refresh(coupon); self.assertEqual(coupon.status,0)

    def test_06_monthly_price_buys_365_days(self):
        self.db.add(PricingRule(store_id=self.stores[0].id,bill_type=BillType.monthly,price=Decimal("100"),valid_days=30))
        self.db.commit()
        item=self.make_order(bill_type=BillType.monthly,end=self.start+timedelta(days=364))
        self.assertEqual((item.end_time.date()-item.start_time.date()).days+1,365)
        self.assertEqual(item.final_price,Decimal("100"))
        self.balance_pay(item.order_no)
        self.assertEqual(self.db.get(Reservation,item.id).pay_status,1)

    def test_07_closed_store_and_calendar_closure_do_not_block_booking(self):
        self.stores[0].status=0
        self.db.add(StoreCalendarDay(store_id=self.stores[0].id,day=self.start.date(),is_closed=1))
        self.db.commit()
        item=self.make_order(); self.balance_pay(item.order_no)
        self.assertEqual(self.db.get(Reservation,item.id).pay_status,1)

    def test_08_store_specific_hours_ignored(self):
        self.stores[0].open_time=time(12); self.stores[0].close_time=time(18); self.db.commit()
        item=self.make_order()
        self.assertEqual(item.start_time.hour,10)

    def test_09_one_hour_card_spent_twice_with_stale_sessions(self):
        a=self.make_order(0); b=self.make_order(1)
        card=PeriodCard(user_id=self.uid,store_id=None,card_type=CardType.hourly,card_name="50 hours",total_hours=Decimal("50"),remaining_hours=Decimal("1"),status=1)
        self.db.add(card); self.db.commit(); cid=card.id
        with self.S() as d1,self.S() as d2:
            c1=d1.get(PeriodCard,cid); c2=d2.get(PeriodCard,cid)
            u1=d1.get(User,self.uid); u2=d2.get(User,self.uid)
            with patch.object(reservation,"finalize_reservation_after_pay",new=AsyncMock()):
                for d,u,item in [(d1,u1,a),(d2,u2,b)]:
                    asyncio.run(reservation.pay(ReservationPayRequest(order_no=item.order_no,pay_type=PayType.period_card,period_card_id=cid),u,d))
        self.db.expire_all()
        self.assertEqual(self.db.get(Reservation,a.id).pay_status,1)
        self.assertEqual(self.db.get(Reservation,b.id).pay_status,1)
        self.assertEqual(self.db.get(PeriodCard,cid).remaining_hours,Decimal("0"))

    def test_10_recharge_duplicate_credit_with_stale_sessions(self):
        o=RechargeOrder(order_no="RCH_AUDIT",user_id=self.uid,amount=Decimal("10"),pay_status=0)
        self.db.add(o); self.db.commit(); oid=o.id
        with self.S() as d1,self.S() as d2:
            o1=d1.get(RechargeOrder,oid); o2=d2.get(RechargeOrder,oid)
            self.assertTrue(fulfill_recharge_order(d1,o1)); d1.commit()
            self.assertTrue(fulfill_recharge_order(d2,o2)); d2.commit()
        self.db.expire_all()
        self.assertEqual(self.db.get(User,self.uid).balance,Decimal("1020"))
        count=self.db.scalar(select(func.count()).select_from(WalletLog).where(WalletLog.ref_order=="RCH_AUDIT"))
        self.assertEqual(count,2)

    def test_11_payment_success_without_key_has_no_retry(self):
        item=self.make_order(); r=self.db.get(Reservation,item.id)
        r.start_time=datetime.now()-timedelta(minutes=5)
        r.end_time=datetime.now()+timedelta(hours=1)
        self.db.add(BleLock(store_id=r.store_id,lock_name="Synthetic",lock_id="audit-real-lock",lock_data=None))
        self.db.commit()
        with patch("app.services.business.TTLockService.send_key",new=AsyncMock(side_effect=ValueError("temporary provider failure"))) as send:
            result=asyncio.run(payment.complete_reservation_wechat_payment(self.db,r,paid_fen=1000))
            self.assertEqual(result,"paid"); self.assertEqual(r.pay_status,1)
            self.assertEqual(self.db.scalar(select(func.count()).select_from(BleKey)),0)
            reservation_result=asyncio.run(reservation.confirm_pay(r.id,self.user,self.db))
            self.assertEqual(reservation_result.data.pay_status,1)
            self.assertEqual(send.call_count,1)
        with self.assertRaises(HTTPException) as err:
            ble.get_ble_key(r.id,self.user,self.db)
        self.assertEqual(err.exception.status_code,404)


    def test_12_same_order_balance_debited_twice_with_stale_sessions(self):
        item=self.make_order()
        with self.S() as d1,self.S() as d2:
            r1=d1.get(Reservation,item.id); r2=d2.get(Reservation,item.id)
            u1=d1.get(User,self.uid); u2=d2.get(User,self.uid)
            self.balance_pay(item.order_no,d1,u1)
            self.balance_pay(item.order_no,d2,u2)
        self.db.expire_all()
        self.assertEqual(self.db.get(User,self.uid).balance,Decimal("980"))
        count=self.db.scalar(select(func.count()).select_from(WalletLog).where(WalletLog.ref_order==item.order_no,WalletLog.type=="consume"))
        self.assertEqual(count,2)

    def test_13_same_order_balance_refunded_twice_with_stale_sessions(self):
        item=self.make_order(); self.balance_pay(item.order_no)
        with self.S() as d1,self.S() as d2:
            r1=d1.get(Reservation,item.id); r2=d2.get(Reservation,item.id)
            u1=d1.get(User,self.uid); u2=d2.get(User,self.uid)
            reservation.cancel(item.id,u1,d1)
            reservation.cancel(item.id,u2,d2)
        self.db.expire_all()
        self.assertEqual(self.db.get(User,self.uid).balance,Decimal("1010"))


    def test_14_foreign_platform_review_and_confirm_allowed_http(self):
        actor=AdminUser(username="audit-store",password_hash="not-used",role="store",store_id=self.stores[0].id,status=1)
        order=MeituanOrder(user_id=self.uid,store_id=self.stores[1].id,coupon_code="AUDIT_FOREIGN",deal_name="Foreign store deal",status=MeituanOrderStatus.verified,verified_at=datetime.now(),meituan_raw={"receipt_channel":"meituan"})
        self.db.add_all([actor,order]); self.db.commit(); oid=order.id
        token=create_access_token("admin:"+str(actor.id))
        app=FastAPI(); app.include_router(admin_receipts.router,prefix="/api"); app.add_middleware(AdminRoleGuardMiddleware)
        def override_db():
            with self.S() as d: yield d
        app.dependency_overrides[get_db]=override_db
        with patch("app.api.admin_role_guard.SessionLocal",self.S):
            c=TestClient(app); headers={"Authorization":"Bearer "+token}
            listing=c.get("/api/admin/receipts/platform-review",headers=headers)
            self.assertEqual(listing.status_code,200)
            self.assertEqual(listing.json()["data"]["items"][0]["store_id"],self.stores[1].id)
            result=c.post("/api/admin/receipts/platform-review/"+str(oid)+"/confirm",headers=headers,json={"channel":"meituan","amount":"10.00","received_on":datetime.now().date().isoformat(),"confirmed":True})
            self.assertEqual(result.status_code,200)
            rid=result.json()["data"]["id"]
            refund=c.post("/api/admin/receipts/"+str(rid)+"/refunds",headers=headers,json={"amount":"1.00","refunded_on":datetime.now().date().isoformat(),"reason":"Audit synthetic refund entry","completed":True,"request_id":str(uuid4())})
            self.assertEqual(refund.status_code,200)
        self.assertIsNotNone(self.db.scalar(select(Receipt).where(Receipt.source_key=="platform:"+str(oid))))


    def test_15_manual_receipt_disappears_from_store_list_http(self):
        actor=AdminUser(username="audit-store",password_hash="not-used",role="store",store_id=self.stores[0].id,status=1)
        self.db.add(actor); self.db.commit()
        token=create_access_token("admin:"+str(actor.id))
        app=FastAPI(); app.include_router(admin_receipts.router,prefix="/api"); app.add_middleware(AdminRoleGuardMiddleware)
        def override_db():
            with self.S() as d: yield d
        app.dependency_overrides[get_db]=override_db
        with patch("app.api.admin_role_guard.SessionLocal",self.S):
            c=TestClient(app); headers={"Authorization":"Bearer "+token}
            created=c.post("/api/admin/receipts",headers=headers,json={"channel":"wechat_transfer","amount":"20.00","received_on":datetime.now().date().isoformat(),"reference":"AUDIT-MANUAL","request_id":str(uuid4())})
            self.assertEqual(created.status_code,200)
            listing=c.get("/api/admin/receipts",headers=headers)
            self.assertEqual(listing.status_code,200)
            self.assertEqual(listing.json()["data"]["total"],0)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Receipt)),1)

if __name__ == "__main__":
    unittest.main(verbosity=2)
