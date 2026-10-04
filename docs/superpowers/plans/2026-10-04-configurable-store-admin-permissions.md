# Configurable Store-Admin Permissions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let HQ toggle each store-admin account’s modules via `permissions[]`, with store-scoped data still locked and a few hard write denials.

**Architecture:** Store module keys + path/API maps in `admin_permissions.py`; `AdminUser.permissions` JSON; login/`/me` return effective permissions; middleware checks module membership instead of a hard HQ-only list; Admins.vue checkbox UI; store-scoped filters for users/wallet/etc. when a store admin has those modules.

**Tech Stack:** FastAPI, SQLAlchemy 2, `schema_migrate`, Vue3 + Element Plus admin-web, `unittest` under `backend/scripts/`.

**Spec:** [docs/superpowers/specs/2026-10-04-configurable-store-admin-permissions-design.md](../specs/2026-10-04-configurable-store-admin-permissions-design.md)

## Global Constraints

- HQ role ignores `permissions` (always full access).
- Store role: missing/`null` permissions ⇒ standard store default set; `[]` ⇒ no modules.
- Hard denials for store role even if module checked: `POST /api/admin/stores`, pricing `copy-to`, pay-account writes, creating/editing HQ admins, editing other stores’ store-admins.
- Store-scoped modules always use `scope_store_id` / `assert_store_access`.
- Global config modules (`banners`, `knowledge`, …) are full-platform when granted; UI must show 「全站配置」.
- Do not invent role templates or field-level ACL.

## File map

| File | Responsibility |
|---|---|
| `backend/app/services/admin_permissions.py` | Keys, defaults, normalize, path→module, effective list |
| `backend/app/models/__init__.py` | `AdminUser.permissions` column |
| `backend/app/services/schema_migrate.py` | ALTER + backfill store defaults |
| `backend/app/api/admin_role_guard.py` | Module gate + hard denials |
| `backend/app/api/routes/admin.py` | login/me profile; create/update admin; store-user filters |
| `backend/app/services/admin_access.py` | helpers if needed for store-user id set |
| `backend/scripts/test_admin_permissions.py` | unit + API tests |
| `admin-web/src/utils/adminAuth.ts` | session permissions + `canAccessPath` |
| `admin-web/src/utils/adminModules.ts` | path→module, labels for UI |
| `admin-web/src/views/Login.vue` | persist permissions |
| `admin-web/src/views/Admins.vue` | checkbox groups + edit |
| `admin-web/src/router/index.ts` | permission-based route guard |
| Global-config views (minimal) | 「全站配置」hint when store role |

---

### Task 1: Permission catalog + unit tests

**Files:**
- Create: `backend/app/services/admin_permissions.py`
- Create: `backend/scripts/test_admin_permissions.py`

**Interfaces:**
- Produces: `STORE_DEFAULT_PERMISSIONS: list[str]`, `ALL_PERMISSIONS: list[str]`, `normalize_permissions(role, raw) -> list[str]`, `has_permission(admin, key) -> bool`, `module_for_admin_path(method, path) -> str | None`, `permission_summary(keys) -> str`

- [ ] **Step 1: Write failing tests**

```python
# backend/scripts/test_admin_permissions.py
from app.services.admin_permissions import (
    STORE_DEFAULT_PERMISSIONS,
    normalize_permissions,
    module_for_admin_path,
    has_permission,
)

class PermissionCatalogTests(unittest.TestCase):
    def test_null_store_gets_defaults(self):
        self.assertEqual(normalize_permissions("store", None), list(STORE_DEFAULT_PERMISSIONS))

    def test_empty_store_gets_none(self):
        self.assertEqual(normalize_permissions("store", []), [])

    def test_hq_ignores_raw(self):
        self.assertIn("admins", normalize_permissions("hq", []))

    def test_path_maps_receipts(self):
        self.assertEqual(module_for_admin_path("GET", "/api/admin/receipts/summary"), "receipts")

    def test_unknown_admin_path_returns_none(self):
        self.assertIsNone(module_for_admin_path("GET", "/api/admin/login"))
```

- [ ] **Step 2: Run tests — expect FAIL** (module missing)

```bash
cd backend
.\.venv\Scripts\python.exe -m unittest scripts.test_admin_permissions -v
```

- [ ] **Step 3: Implement catalog**

`admin_permissions.py` must include:

```python
STORE_DEFAULT_PERMISSIONS = [
    "dashboard", "receipts", "live_board", "stores", "calendar", "pricing",
    "seats", "reservations", "locks", "door_logs", "card_orders",
    "period_cards", "deal_mappings", "exchange",
]

EXTENDED_PERMISSIONS = [
    "admins", "pay_accounts", "users", "wallet_logs", "point_logs", "invites",
    "coupons", "banners", "announcements", "notifications", "contact",
    "booking_setting", "study", "knowledge", "wrongbook", "market",
    "system", "operation_logs",
]

ALL_PERMISSIONS = STORE_DEFAULT_PERMISSIONS + EXTENDED_PERMISSIONS

# PATH_RULES: list of (prefix_or_predicate, module_key)
# Cover every /api/admin/* used by admin-web menus. Prefer longest-prefix match.
# Examples:
#   "/api/admin/receipts" -> receipts
#   "/api/admin/stats" -> dashboard
#   "/api/admin/stats/todos" -> dashboard
#   "/api/admin/stores/{id}/live-board" -> live_board
#   "/api/admin/stores/{id}/calendar" -> calendar
#   "/api/admin/stores/{id}/pricing" -> pricing
#   "/api/admin/stores/{id}/seats" / "/api/admin/seats" / seat-map -> seats
#   "/api/admin/reservations" -> reservations
#   "/api/admin/locks" / ble locks -> locks
#   "/api/admin/door-logs" -> door_logs
#   "/api/admin/card-purchase-orders" -> card_orders
#   "/api/admin/period-cards" -> period_cards
#   "/api/admin/deal-mappings" / pending-deal -> deal_mappings
#   "/api/admin/exchange" -> exchange
#   "/api/admin/admins" -> admins
#   "/api/admin/pay-accounts" -> pay_accounts
#   "/api/admin/users" -> users
#   "/api/admin/wallet-logs" / export wallet -> wallet_logs
#   "/api/admin/point-logs" -> point_logs
#   "/api/admin/invites" -> invites
#   "/api/admin/coupons" -> coupons
#   "/api/admin/banners" -> banners
#   "/api/admin/announcements" -> announcements
#   "/api/admin/notifications" -> notifications
#   "/api/admin/contact-setting" -> contact
#   "/api/admin/booking-setting" -> booking_setting
#   "/api/admin/study" / assistant -> study
#   "/api/admin/knowledge" -> knowledge
#   "/api/admin/wrongbook" -> wrongbook
#   "/api/admin/market" -> market
#   "/api/admin/system" -> system
#   "/api/admin/operation-logs" -> operation_logs
#   GET /api/admin/stores (list/detail/update) -> stores
# login/me: return None (always allowed)
```

`normalize_permissions(role, raw)`:
- hq → `list(ALL_PERMISSIONS)`
- store + `None` → `list(STORE_DEFAULT_PERMISSIONS)`
- store + list → intersect with `ALL_PERMISSIONS`, preserve order of ALL

`has_permission(admin, key)` uses `admin_role` + `normalize_permissions(admin.role, admin.permissions)`.

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/admin_permissions.py backend/scripts/test_admin_permissions.py
git commit -m "feat: admin permission catalog and path map"
```

---

### Task 2: Model + migration + backfill

**Files:**
- Modify: `backend/app/models/__init__.py` (`AdminUser`)
- Modify: `backend/app/services/schema_migrate.py`
- Modify: `backend/scripts/test_admin_permissions.py` (migration case)

**Interfaces:**
- Consumes: `STORE_DEFAULT_PERMISSIONS` as JSON for backfill
- Produces: `AdminUser.permissions: Mapped[list | None]` (JSON column)

- [ ] **Step 1: Failing test** — after create_all + migrate, store admin with null column normalizes to defaults; column exists on `admin_users`

- [ ] **Step 2: Add model field**

```python
permissions: Mapped[list | None] = mapped_column(JSON, nullable=True)
```

- [ ] **Step 3: Migration**

```python
"ALTER TABLE admin_users ADD COLUMN permissions JSON",
```

After ALTER, if table exists:

```python
# backfill: UPDATE admin_users SET permissions = '<json of STORE_DEFAULT>' WHERE role='store' AND permissions IS NULL
# hq left NULL
```

Use `json.dumps(STORE_DEFAULT_PERMISSIONS)` for SQLite JSON text.

- [ ] **Step 4: Run `scripts.test_admin_permissions` + `scripts.test_admin_roles` — PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: admin_users.permissions column and store backfill"
```

---

### Task 3: Guard middleware uses modules + hard denials

**Files:**
- Modify: `backend/app/api/admin_role_guard.py`
- Modify: `backend/scripts/test_admin_permissions.py`

**Interfaces:**
- Consumes: `module_for_admin_path`, `has_permission`, `is_hq`
- Replaces: hard `HQ_ONLY_PREFIXES` allow/deny with permission check

- [ ] **Step 1: API-style tests with TestClient**

Cases:
1. Store admin without `receipts` → `GET /api/admin/receipts/summary` → 403
2. Store admin with defaults → `GET /api/admin/stats` → 200 (mount minimal router or full app with overrides)
3. Store admin with `banners` → banners GET allowed (if router included)
4. Any store admin → `POST /api/admin/stores` → 403
5. Any store admin → path containing `/pricing/copy-to/` → 403
6. HQ → former HQ-only path still 200

Keep tests focused: include `admin_receipts` + a tiny stub or `admin` router with dependency overrides like `test_receipts.py`.

- [ ] **Step 2: Rewrite middleware logic**

```python
# Pseudocode
if path in login/me: next
if not path.startswith("/api/admin"): next
# hard denials for store (check role after auth decode)
if store and (POST stores create or copy-to or pay-accounts write methods):
    return 403
module = module_for_admin_path(method, path)
if module is None:
    next  # unmapped: allow only if already authenticated; prefer mapping all admin routes
if is_hq(admin):
    next
if not has_permission(admin, module):
    return 403 「无此模块权限」
next
```

Remove or shrink `HQ_ONLY_PREFIXES` so granted extended modules work. Keep hard denials from the spec.

- [ ] **Step 3: Tests PASS**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: enforce store-admin module permissions in API guard"
```

---

### Task 4: Login/me + create/update admin APIs

**Files:**
- Modify: `backend/app/api/routes/admin.py` (`_admin_profile`, `AdminCreateRequest`, `create_admin_user`, new `PATCH /admins/{id}`)
- Modify: `backend/scripts/test_admin_permissions.py`

**Interfaces:**
- `_admin_profile` adds `"permissions": normalize_permissions(...)`
- `AdminCreateRequest.permissions: list[str] | None = None`
- `AdminUpdateRequest`: optional name/role/store_id/password/permissions/status
- Create store: if permissions omitted → save `STORE_DEFAULT_PERMISSIONS`; if provided → normalize intersect
- Create hq: permissions stored `None`
- PATCH: HQ-only for now **unless** actor is store with `admins` module (Task 5 tightens actor rules)

- [ ] **Step 1: Tests**

```python
def test_create_store_default_permissions(self):
    # POST /admin/admins role=store -> data.permissions == STORE_DEFAULT

def test_create_store_custom_permissions(self):
    # permissions=["dashboard"] -> only dashboard (+ normalized)

def test_me_returns_permissions(self):
    ...
```

- [ ] **Step 2: Implement profile + create + patch**

`PATCH /admin/admins/{id}`:
- require `admins` module (HQ always has it)
- store actor rules deferred to Task 5; until then `require_hq_admin` OR `has_permission(admins)` + store constraints in Task 5

List admins: include `permissions` + `permission_summary` string for UI.

- [ ] **Step 3: Tests PASS**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: expose and persist admin permissions on login and CRUD"
```

---

### Task 5: Store actor rules for admins + pay_accounts + users scope

**Files:**
- Modify: `backend/app/api/routes/admin.py` (list/create/patch admins; list users; wallet/point/invite/coupon list filters)
- Modify: `backend/app/api/admin_role_guard.py` if pay-account writes need method checks
- Create helper in `admin_permissions.py` or `admin_access.py`:

```python
def store_related_user_ids(db, store_id: int) -> set[int]:
    # union user_id from Reservation, CardPurchaseOrder, MeituanOrder where store_id=...
```

**Rules:**
- Store + `admins`: `GET/POST/PATCH /admins` only sees/edits `role=store` and `store_id==actor.store_id`; cannot set `role=hq`; new store admins forced to actor’s store_id
- Store + `pay_accounts`: GET list filtered to accounts bound by actor’s store; POST/PATCH/DELETE → 403
- Store + `users` (and wallet/point/invites/coupons): filter by `store_related_user_ids`
- Store + `notifications`: if body has store_id, must equal actor store; default store_id to actor store
- Store + `operation_logs`: filter rows where actor is this admin or target_id/store in detail matches store (best-effort; document in test)

- [ ] **Step 1: Tests for user filter + admin create-by-store-manager + pay write 403**

- [ ] **Step 2: Implement filters**

- [ ] **Step 3: Tests PASS**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: store-scoped data for extended admin modules"
```

---

### Task 6: Admin-web auth + menu + router

**Files:**
- Create: `admin-web/src/utils/adminModules.ts` (mirror keys + `pathToModule`)
- Modify: `admin-web/src/utils/adminAuth.ts`
- Modify: `admin-web/src/views/Login.vue`
- Modify: `admin-web/src/router/index.ts`
- Modify: `admin-web/src/layouts/AdminLayout.vue` (menu already uses `canAccessPath`)

**Interfaces:**
- `saveAdminSession` stores `admin_permissions` JSON
- `getAdminPermissions(): string[] | null` — null means HQ full
- `canAccessPath(path)`: HQ true; else module from path must be in permissions
- On login, also refresh from `/admin/me` if convenient

```ts
// adminModules.ts
export const STORE_DEFAULT_PERMISSIONS = [ /* same keys */ ]
export const PATH_MODULE: Record<string, string> = {
  '/dashboard': 'dashboard',
  '/receipts': 'receipts',
  '/live-board': 'live_board',
  '/stores': 'stores',
  '/store-calendar': 'calendar',
  '/pricing': 'pricing',
  '/seats': 'seats',
  '/reservations': 'reservations',
  '/locks': 'locks',
  '/door-logs': 'door_logs',
  '/card-purchase-orders': 'card_orders',
  '/period-cards': 'period_cards',
  '/deal-mappings': 'deal_mappings',
  '/exchange-records': 'exchange',
  '/admins': 'admins',
  '/pay-accounts': 'pay_accounts',
  '/users': 'users',
  '/wallet-logs': 'wallet_logs',
  '/point-logs': 'point_logs',
  '/invites': 'invites',
  '/coupons': 'coupons',
  '/banners': 'banners',
  '/announcements': 'announcements',
  '/notifications': 'notifications',
  '/contact-setting': 'contact',
  '/booking-setting': 'booking_setting',
  '/study-data': 'study',
  '/assistant-usage': 'study',
  '/knowledge': 'knowledge',
  '/wrongbook': 'wrongbook',
  '/market-listings': 'market',
  '/market-ops': 'market',
  '/system-status': 'system',
  '/operation-logs': 'operation_logs',
}
```

Remove static `HQ_ONLY_PATHS` deny list; replace with permission check.

- [ ] **Step 1: Implement + manual smoke** (login as store, menu matches permissions)

- [ ] **Step 2: Commit**

```bash
git commit -m "feat: admin-web menu and router respect permissions"
```

---

### Task 7: Admins.vue checkbox UI + edit

**Files:**
- Modify: `admin-web/src/views/Admins.vue`
- Optionally widen dialog to `640px`

- [ ] **Step 1: UI**

- Role `store`: two `el-checkbox-group`s — 本店模块 / 扩展模块（扩展项旁灰色「全站配置」for banners/knowledge/…）
- Button 「恢复标准店长」→ set permissions to `STORE_DEFAULT_PERMISSIONS`
- Default on openAdd for store: defaults selected
- Table column 「权限」: `标准` if equals default set; else `标准+N` or `自定义(N)`
- Edit dialog: PATCH permissions (add row action 「编辑」)
- Hide create HQ / edit HQ when current user is store (even with admins)

- [ ] **Step 2: Wire API create/patch with `permissions`**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: configure store-admin modules in Admins UI"
```

---

### Task 8: Global-config page hints + verify

**Files:**
- Modify lightly: `Banners.vue`, `Announcements.vue`, `Knowledge.vue`, `ContactSetting.vue`, `BookingSetting.vue`, market views — one-line `el-alert` if `!isHqAdmin()`  
- Or a tiny `GlobalConfigHint.vue` component reused

- [ ] **Step 1: Add hint component / alerts**

- [ ] **Step 2: Run full backend permission tests**

```bash
cd backend
.\.venv\Scripts\python.exe -m unittest scripts.test_admin_permissions scripts.test_admin_roles -v
```

- [ ] **Step 3: Update spec status to `已确认并实现`**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: global-config hints for store admins; finish permissions"
```

---

## Spec coverage checklist

| Spec item | Task |
|---|---|
| permissions column + null/[] semantics | 1–2 |
| Default store set on create / backfill | 2, 4 |
| All modules selectable | 4, 7 |
| Path/menu/API gating | 1, 3, 6 |
| Hard denials | 3 |
| Store-scoped users/admins/pay read | 5 |
| Global modules full-platform + UI label | 5, 7, 8 |
| Admins UI groups + restore standard | 7 |
| login/me permissions | 4, 6 |
| Tests | 1–5, 8 |

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-04-configurable-store-admin-permissions.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — run tasks in this session with checkpoints  

Which approach?
