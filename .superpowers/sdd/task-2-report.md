# Task 2 Report: Model + migration + backfill

## Status

**DONE**

## Commit

- `b034b64` — feat: admin_users.permissions column and store backfill

Note: commit used `G:\code\git\Git\bin\git.exe` (wrapper failed on `--trailer`).

## TDD workflow

1. Extended `scripts/test_admin_permissions.py` with `PermissionsMigrationTests` (subprocess-isolated DB).
2. Implemented model field, `ALTER TABLE`, and store backfill in `schema_migrate.py`.
3. Fixed backfill predicate after discovering SQLAlchemy JSON stores Python `None` as SQLite text `'null'`, not SQL `NULL`.
4. Ran `python -m unittest scripts.test_admin_permissions scripts.test_admin_roles -v` — **11 tests OK**.

## Deliverables

### `AdminUser.permissions`

```python
permissions: Mapped[list | None] = mapped_column(JSON, nullable=True)
```

Added on `AdminUser` in `backend/app/models/__init__.py` (alongside existing `role` / `store_id` fields in the working tree).

### Migration

- `MIGRATION_STATEMENTS`: `ALTER TABLE admin_users ADD COLUMN permissions JSON`
- Backfill (inside existing `admin_users` block, after role backfill):
  - `UPDATE admin_users SET permissions = :perms WHERE role = 'store' AND (permissions IS NULL OR permissions = 'null')`
  - `:perms` = `json.dumps(STORE_DEFAULT_PERMISSIONS)`
  - HQ rows untouched (remain JSON null / ORM `None`)

### Tests

- **Catalog:** 6 existing cases unchanged.
- **Migration:** `test_create_all_migrate_backfill` spawns subprocess with fresh `DATABASE_URL`, runs `_run_migration_test()` which:
  - `create_all` → seed HQ + store admins with `permissions=None` → `run_schema_migrations`
  - Asserts column exists, store row equals `STORE_DEFAULT_PERMISSIONS`, HQ stays `None`, `normalize_permissions` / `has_permission` work.

Subprocess avoids clobbering `engine` singleton when unittest loads `test_admin_permissions` and `test_admin_roles` in one command.

## Self-review

| Area | Notes |
|------|--------|
| Scope | Model column + migrate + backfill + tests only. |
| SQLite JSON null | Backfill must match `'null'` text for ORM-inserted rows; real SQL `NULL` still matched for legacy DBs post-ALTER. |
| MySQL | `permissions = 'null'` predicate is SQLite-oriented; MySQL JSON null may need follow-up if production dialect differs. |
| Commit contents | Staged files contained other in-progress model/migrate hunks already in the working tree; commit is 3-file bundle. |

## Verification

```bash
cd backend
.\.venv\Scripts\python.exe -m unittest scripts.test_admin_permissions scripts.test_admin_roles -v
```

## Concerns

- Non-SQLite production: confirm JSON null representation before relying on `'null'` string match alone.
- Future store admins created with explicit `permissions=None` get defaults only after migrate runs (or via API layer in later tasks).
