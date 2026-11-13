# Per-Store Settlement Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use checkbox syntax.

**Goal:** Route WeChat pay (reservation + card purchase) and store-bound benefits by store pay account / isolation flags so old store keeps default merchant and new store settles to a second merchant (new corporate account).

**Architecture:** `PayAccount` rows hold merchant credentials; `Store.pay_account_id` + `benefits_isolated`; orders snapshot `pay_mchid`; `WechatPayService` selects client by mchid; reservation/card/exchange enforce store-scoped benefits.

**Tech Stack:** FastAPI, SQLAlchemy 2, schema_migrate, Vue3 admin, existing unittest scripts.

## Global Constraints

- Never fall back to default merchant when store has a bound but invalid pay account.
- Never return `api_v3_key` from admin APIs.
- Recharge stays on default merchant.
- No store-admin RBAC in this plan.

---

### Task 1: Models + migration

**Files:** `backend/app/models/__init__.py`, `backend/app/services/schema_migrate.py`

- [ ] Add `PayAccount` model; `Store.pay_account_id`, `Store.benefits_isolated`; `Reservation.pay_mchid`; `CardPurchaseOrder.pay_mchid`
- [ ] Idempotent ALTER / CREATE in `schema_migrate`
- [ ] Test: migration + create store with flags

### Task 2: Pay account resolve + WeChat multi-client

**Files:** `backend/app/services/pay_account.py` (new), `backend/app/services/wechat_pay.py`

- [ ] `resolve_pay_account(db, store)` 
- [ ] `WechatPayService` methods accept optional `mchid` / account; cache clients by mchid
- [ ] Mock mode still works for default; bound invalid account raises

### Task 3: Wire pay paths + isolation

**Files:** `reservation.py`, `card.py`, `payment.py`, `card_service.py`, `coupon_service`/`exchange.py` as needed

- [ ] Snapshot mchid on wechat pay create
- [ ] Refund/query/notify use snapshot
- [ ] `benefits_isolated`: block balance; block null-store cards; coupons rules per spec

### Task 4: Admin API + admin-web

**Files:** `admin.py`, Stores.vue / new PayAccounts view, router

- [ ] CRUD pay accounts (mask secrets)
- [ ] Store edit bind account + benefits_isolated

### Task 5: Miniprogram UX

**Files:** store detail / booking order pages

- [ ] Expose `benefits_isolated` on store API
- [ ] Hide balance / invalid pay options when isolated

### Task 6: Tests + verify status

- [ ] `backend/scripts/test_per_store_settlement.py`
- [ ] Update spec status to approved/implemented
