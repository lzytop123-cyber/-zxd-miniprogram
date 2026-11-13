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

