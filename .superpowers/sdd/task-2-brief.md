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

