# Multi-Company Stores Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run two independently operated stores in one mini program while isolating admin data and routing each reservation payment and refund to its owning company.

**Architecture:** Add a company owner to stores and admins, and snapshot the company and merchant profile on each reservation. Keep one public AppID and one database. Scope every admin operation on the server; route WeChat orders, callbacks, queries and refunds through the reservation's immutable merchant profile. The existing store-seat-map plan is a separate prerequisite for opening the new store.

**Tech Stack:** FastAPI, SQLAlchemy 2, SQLite/MySQL, wechatpayv3, Vue 3/Element Plus, native WeChat mini program, Python `unittest`, Node `--test`.

**Spec:** `docs/superpowers/specs/2026-10-03-multi-company-stores-design.md`

## Global Constraints

- One mini program AppID; two ordinary WeChat Pay merchant accounts.
- Existing stores, admins, reservations, recharges and card purchases migrate to the original company without changing balances or order numbers.
- The sister's store stays closed until seat-map, permissions, payment binding, price and real refund acceptance all pass.
- Sister-company reservations accept WeChat payment only; existing balance, cards, coupons, points and vouchers cannot be used or issued there.
- Merchant credentials remain server-side. A missing profile fails payment closed; it never falls back to the original company's merchant account.
- Normal customer flows show store names. Each store detail exposes a qualification link; first data transfer to the sister company uses a separate notice and consent.
- No self-service merchant onboarding, subscriptions, cross-company cart or entitlement sharing.

## Review Focus

1. An admin changes `store_id`, order ID, export filters or a direct URL to another company's resource: return 403/404 without leaking data (Task 2 and Task 3 tests).
2. A sister-store booking attempts an old global card, wallet balance, coupon or mock offline payment: reject before deducting or fulfilling anything (Task 4 tests).
3. A callback signed by one merchant references another merchant's order, or has the wrong amount: do not mark paid or grant access (Task 5 tests).
4. A paid reservation is refunded after its store's current merchant profile changes: refund through the original snapshotted profile (Task 5 test).
5. A new store has no published seat map or approved payment profile: it remains unavailable to public booking (Task 6 acceptance test; seat-map plan test).

---

## File Structure

- `backend/app/models/__init__.py`, `backend/app/services/schema_migrate.py`: company, admin ownership, store ownership, reservation payment snapshot and consent persistence.
- `backend/app/api/deps.py`, new `backend/app/services/company_access.py`: authenticated company context, resource authorization and list filters.
- `backend/app/api/routes/admin.py`, `admin_tools.py`, `admin_receipts.py`, `ble.py`, `notifications.py`, `admin_market.py`: allowed business endpoints and explicit denial of global modules to sister-company admins.
- `backend/app/services/wechat_pay.py`, `backend/app/api/routes/payment.py`, `reservation.py`, `card.py`, `report.py`: per-profile payment, notification, query, refund and entitlement restrictions.
- `backend/app/api/routes/store.py`, `backend/app/schemas/store.py`: qualifications and customer payment capabilities.
- `admin-web/src/layouts/AdminLayout.vue`, `admin-web/src/router/index.ts`, `admin-web/src/views/Stores.vue`, new `admin-web/src/views/Companies.vue`: role-aware navigation, company setup and store operations; server authorization remains authoritative.
- `miniprogram/pages/store/detail.*`, `miniprogram/pages/booking/order.*`, new `miniprogram/pages/store/qualification.*`: per-store map/qualification/payment presentation and first-order consent.
- `backend/scripts/test_multi_company.py`, `miniprogram/tests/multiCompany.test.js`: cross-company, payment and customer-flow regression tests. Run backend tests with the bundled `unittest` runner; this project does not install `pytest`.

### Task 1: Persist company ownership and preserve existing records

**Files:** Modify `backend/app/models/__init__.py`, `backend/app/services/schema_migrate.py`, `backend/scripts/init_production.py`; create `backend/scripts/test_multi_company.py`.

**Interfaces:** Create `OperatingCompany(id, legal_name, status, payment_profile, payment_binding_verified_at, license_image_url, permit_info, contact)`; add `Store.company_id`, `AdminUser.company_id`, `AdminUser.role`, `Reservation.company_id`, `Reservation.payment_profile`, `Reservation.pay_mchid`; create `UserCompanyConsent(user_id, company_id, notice_version, granted_at)` with unique `(user_id, company_id, notice_version)`.

- [ ] **Step 1: Write `test_legacy_backfill_idempotent`** using a legacy SQLite fixture: startup creates original company ID 1, assigns old stores/admins/reservations to it, preserves balances/order numbers/paid states, and a second migration makes no further changes.
- [ ] **Step 2: Run** `cd backend && .venv\Scripts\python -m unittest scripts.test_multi_company -v`; expect the new migration test to fail.
- [ ] **Step 3: Add models and additive SQLite/MySQL-compatible migration/backfill in `schema_migrate.py`.** Backfill legacy card/recharge ownership logically to company 1; do not rename or rebuild existing payment records. Reject null company ownership at service boundaries after migration.
- [ ] **Step 4: Run the test plus existing** `backend/scripts/test_sprint1.py` and `backend/scripts/test_card_rules.py`; expect pass.
- [ ] **Step 5: Commit** `feat: add operating company ownership`.

### Task 2: Centralize backend company authorization

**Files:** Modify `backend/app/api/deps.py`; create `backend/app/services/company_access.py`; modify admin login and company provisioning endpoints in `backend/app/api/routes/admin.py`; extend `backend/scripts/test_multi_company.py`.

**Interfaces:** `require_company_store(db: Session, admin: AdminUser, store_id: int) -> Store`, `require_company_reservation(db: Session, admin: AdminUser, reservation_id: int) -> Reservation`, `company_store_ids(db: Session, admin: AdminUser) -> Select[int]`, `require_platform_config(admin: AdminUser) -> None`. `GET /api/admin/me` returns role and company ID, not merchant secrets.

- [ ] **Step 1: Add `test_company_access_helpers` and `test_platform_config_cannot_browse_sister_orders`:** assert original/sister admins cannot load the other's store or reservation, disabled admin is rejected, platform configuration can register a company but remains scoped to original-company business data.
- [ ] **Step 2: Run the targeted test; expect failure.**
- [ ] **Step 3: Implement the access helpers and company creation/status/payment-profile-reference management.** The existing admin becomes original-company platform admin; sister-company admin is provisioned explicitly. Payment secrets are configured outside the API.
- [ ] **Step 4: Run targeted test; expect pass.**
- [ ] **Step 5: Commit** `feat: add company admin context`.

### Task 3: Enforce company isolation on every admin route

**Files:** Modify `backend/app/api/routes/admin.py`, `admin_tools.py`, `admin_receipts.py`, `ble.py`, `notifications.py`, `admin_market.py`; extend `backend/scripts/test_multi_company.py`.

**Interfaces:** Business lists use `company_store_ids`; detail/mutations use `require_company_store` or `require_company_reservation`; sister admins receive 403 for global wallet, cards, points, coupons, deal mapping, marketplace, AI, banners, sitewide settings and admin provisioning.

- [ ] **Step 1: Inventory each admin endpoint in the listed route files and add `test_admin_cross_company_isolation`:** for store/reservation lists, detail IDs, mutations, exports and stats, sister admin sees only sister rows or gets 403/404. Add `test_global_admin_modules_denied` for wallet, cards, points, coupons, market, knowledge, banners and site settings.
- [ ] **Step 2: Scope store, seat, pricing, calendar, reservation, customer-by-order, lock, receipt and report endpoints.** Treat missing scope as denial; customer profile responses contain only fields needed for that company's orders.
- [ ] **Step 3: Deny sister admins at server entry points for all global modules and any endpoint not explicitly scoped.** Apply the same guard to seat-map admin endpoints added by the prerequisite plan.
- [ ] **Step 4: Run targeted cross-company tests and existing admin/receipt/lock tests; expect pass.**
- [ ] **Step 5: Commit** `feat: isolate company admin data`.

### Task 4: Prevent old entitlements from crossing companies

**Files:** Modify `backend/app/api/routes/reservation.py`, `card.py`, `report.py`, `exchange.py`, `user.py`, `backend/app/services/booking.py`, `points.py`, `backend/app/api/routes/store.py`, `backend/app/schemas/store.py`; extend `backend/scripts/test_multi_company.py`.

**Interfaces:** `StoreDetail` exposes `payment_options` and qualification metadata; the server derives both from the store's company. `POST /api/user/company-consents` records `company_id` and current `notice_version` after explicit consent; booking requires it for sister company. New-company booking allows only `PayType.wechat`; recharge, card purchase, voucher redemption and points accrual are original-company-only in the first release.

- [ ] **Step 1: Add `test_sister_store_rejects_legacy_entitlements`** for wallet/card/coupon/points/voucher attempts, including a `PeriodCard.store_id is None` legacy card; assert balances and card counts remain unchanged. Add `test_sister_booking_requires_consent` and assert consent records are versioned and cannot be forged for another user.
- [ ] **Step 2: Run targeted tests; expect failure.**
- [ ] **Step 3: Gate entitlement and booking paths on server-owned company.** Do not rely on hidden mini-program controls. Keep original-company behavior and existing customer history unchanged.
- [ ] **Step 4: Run targeted and existing card/booking tests; expect pass.**
- [ ] **Step 5: Commit** `feat: keep legacy entitlements in original company`.

### Task 5: Route WeChat payment by immutable order merchant

**Files:** Modify `backend/app/core/config.py`, `backend/app/services/wechat_pay.py`, `backend/app/api/routes/payment.py`, `reservation.py`, `card.py`, `report.py`, `backend/.env.production.example`, `docker-compose.prod.yml`; extend `backend/scripts/test_multi_company.py`.

**Interfaces:** `WechatPayService.create_jsapi_order(..., profile_key: str)`, `query_order(order_no: str, profile_key: str)`, `verify_notify(headers: dict, body: bytes, profile_key: str)`, `refund(..., profile_key: str)`; old card/recharge calls use explicit original profile. New callback path `/api/payment/wechat/{profile_key}/notify`; old `/api/payment/wechat/notify` remains as original-profile alias. Profile config resolves to `mchid` and secret paths server-side.

- [ ] **Step 1: Add `test_payment_profile_routing`, `test_wrong_merchant_callback_rejected`, `test_duplicate_callback_idempotent` and `test_refund_uses_order_profile`:** assert sister reservation selects sister profile, old recharge/card select original profile, missing profile fails closed, merchant/amount mismatch does not fulfill, replay does not duplicate effects, and profile changes do not reroute historical refunds.
- [ ] **Step 2: Run targeted tests; expect failure.**
- [ ] **Step 3: Refactor the singleton payment client into a cache keyed by profile and route all reservation create/query/refund paths through the reservation snapshot.** Validate merchant ID and amount after verified callback before applying business effects; keep the legacy callback URL for historical orders.
- [ ] **Step 4: Run targeted and existing payment/receipt tests; expect pass.** Check environment examples contain placeholders only and no private keys in responses or logs.
- [ ] **Step 5: Commit** `feat: route payments by company merchant`.

### Task 6: Complete store-facing UI and launch gates

**Files:** Modify `admin-web/src/layouts/AdminLayout.vue`, `admin-web/src/router/index.ts`, `admin-web/src/views/Stores.vue`, `admin-web/src/views/Admins.vue`, `miniprogram/pages/store/detail.*`, `miniprogram/pages/booking/order.*`, `miniprogram/app.json`; create `admin-web/src/views/Companies.vue`, `miniprogram/pages/store/qualification.*`, `miniprogram/tests/multiCompany.test.js`; modify `docs/POST-DEPLOY.md`.

**Interfaces:** Admin UI calls `/api/admin/me` for menu/routing; store detail links to company qualification; booking page uses server `payment_options` and displays the sister-company data notice on its first booking, recording `UserCompanyConsent` before sending customer data to sister admin.

- [ ] **Step 1: Add `multiCompany.test.js` cases** for switching between two different store layouts, independent payment options, no old card/wallet/coupon in sister checkout, qualification link and first-booking consent. Add manual admin acceptance checks for company-specific menus, company setup and navigation.
- [ ] **Step 2: Implement the UI and notice/consent endpoint flow.** Do not show legal company name in the routine store selection or checkout layout; display it in qualifications and the required first-transfer notice.
- [ ] **Step 3: Run** `cd admin-web && npm run build` and `cd miniprogram && npm test`; expect pass. Manually verify switch-store layout cannot show a stale map from the other store.
- [ ] **Step 4: Update `docs/POST-DEPLOY.md` with binding, real small-value payment/refund and separate ledger checks.** Require the existing seat-map plan, merchant binding, correct store hours/prices and all cross-company checks before opening sister store.
- [ ] **Step 5: Commit** `feat: present separate stores in one mini program`.

## Execution Order

Implement the already written `docs/superpowers/plans/2026-10-01-configurable-store-seat-maps.md` before opening the new store. Its map editor, per-store image/markers and publication gate satisfy the distinct-layout requirement; the current fixed layout remains for the original store. Tasks 1–6 above then add company ownership, isolation, merchant routing and release gates. Code from both plans may be developed in separate commits, but the sister store must stay closed until both plans pass their acceptance checks.
