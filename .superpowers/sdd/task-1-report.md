# Task 1 Report: Permission catalog + unit tests

## Status

**DONE**

## Commit

- `ded87cf` — feat: admin permission catalog and path map

## TDD workflow

1. Added `backend/scripts/test_admin_permissions.py` with the five cases from the task brief.
2. Ran `python -m unittest scripts.test_admin_permissions -v` — failed with `ModuleNotFoundError` (expected).
3. Implemented `backend/app/services/admin_permissions.py`.
4. Re-ran tests — 5 passed.

## Deliverables

### `admin_permissions.py`

- **Constants:** `STORE_DEFAULT_PERMISSIONS`, `EXTENDED_PERMISSIONS`, `ALL_PERMISSIONS` — values match the brief verbatim.
- **`normalize_permissions(role, raw)`**
  - `hq` → full `ALL_PERMISSIONS` (ignores `raw`).
  - `store` + `None` → `STORE_DEFAULT_PERMISSIONS`.
  - `store` + list → intersection with `ALL_PERMISSIONS`, order preserved from `ALL_PERMISSIONS`.
  - `store` + `[]` → `[]`.
- **`has_permission(admin, key)`** — uses `admin.role` and `getattr(admin, "permissions", None)` so it works before the model column lands in Task 2.
- **`module_for_admin_path(method, path)`** — `login` / `me` return `None`; otherwise first matching rule in `PATH_RULES` (longest/specific rules listed first). String prefixes use segment-safe matching; store sub-routes use regex for numeric `store_id`. `method` is accepted but unused (reserved).
- **`permission_summary(keys)`** — UI helper: `无` / `标准` / `标准+N` / `N项` per design doc list labels.

### Path coverage

Rules align with admin-web menus and current FastAPI routes under `/api/admin/*`, including:

- Receipts, dashboard stats/todos, store-scoped live-board/calendar/pricing/seats/seat-map/zones
- Reservations, locks, door-logs, card/period/deal/exchange modules
- Extended modules (admins, pay-accounts, users, logs, market, wrongbook, etc.)
- Exports (`wallet-logs`, `reservations`, `study-stats`)
- `exchange-records` mapped to `exchange` (actual API path; brief example used `/exchange`)

### Tests

`PermissionCatalogTests`: null defaults, empty list, HQ full access, receipts path, login unmapped.

## Self-review

| Area | Notes |
|------|--------|
| Scope | Only catalog + unit tests; no model, migration, or middleware (later tasks). |
| `has_permission` import in tests | Imported per brief but not asserted yet — fine for Task 1. |
| Unknown admin paths | Return `None` (middleware will treat as allow or separate handling in Task 3). |
| `system/coupon` | Mapped to `coupons` module (HQ-style coupon config endpoint). |
| Git commit | Wrapper `git commit` failed on `--trailer`; used `G:\code\git\Git\bin\git.exe` as instructed. |

## Verification command

```bash
cd backend
.\.venv\Scripts\python.exe -m unittest scripts.test_admin_permissions -v
```

Result: **5 tests, OK**

## Concerns

None blocking. Future tasks should add tests for `permission_summary`, `has_permission`, and broader path-rule regression once middleware exists.

---

## Review fix: expiring-cards → live_board

**Status:** DONE  
**Commit:** `9f25ed2` — fix: map store expiring-cards API to live_board

**Change:** Added `PATH_RULE` for `^/api/admin/stores/{id}/expiring-cards` → `live_board`, immediately after the existing `live-board` rule and before the `/api/admin/stores` catch-all (which had incorrectly mapped this endpoint to `stores`).

**Regression test:** `test_path_maps_store_expiring_cards_to_live_board` asserts  
`module_for_admin_path("GET", "/api/admin/stores/1/expiring-cards") == "live_board"`.

**Verification:**

```bash
cd backend
.\.venv\Scripts\python.exe -m unittest scripts.test_admin_permissions -v
```

```
test_empty_store_gets_none ... ok
test_hq_ignores_raw ... ok
test_null_store_gets_defaults ... ok
test_path_maps_receipts ... ok
test_path_maps_store_expiring_cards_to_live_board ... ok
test_unknown_admin_path_returns_none ... ok

Ran 6 tests in 0.001s

OK
```
