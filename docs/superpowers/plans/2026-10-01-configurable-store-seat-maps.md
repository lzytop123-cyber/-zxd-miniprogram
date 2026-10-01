# Configurable Store Seat Maps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let each store publish its own uploaded floor image and positioned seats, while preserving the existing store's fixed 28-seat map and historical reservations.

**Architecture:** Keep `Seat` as the booking identity. Store image maps as versioned draft/published snapshots containing an image path and seat-ID-to-position mapping. Public and booking code branches on the store's map mode; the new store stays closed until the later payment and ownership phase is complete.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite/MySQL, Vue 3 + Element Plus, WeChat native mini program, Python `unittest`, Node `--test`.

**Spec:** `docs/superpowers/specs/2026-10-01-configurable-store-seat-maps-design.md`

## Global Constraints

- Existing stores start in `legacy` mode; their fixed map, bookings, and seat IDs remain unchanged.
- New stores start in `image` mode with `status=0`; publishing a map never opens a store.
- Image-map seat codes are unique within their store and may be outside 1–28; reservation identity is `Seat.id`.
- A draft cannot affect customer-visible image, positions, or availability until atomic publication.
- Deleting a seat with historical reservations is forbidden; disabling it must preserve order history.
- This plan does not enable the sister's store, configure her merchant account, or grant store-scoped admin access.

## Review Focus

1. A draft image with moved markers must leave the published image and positions unchanged until publication (Task 2 test).
2. A seat belonging to another store, or omitted from the published image map, must be rejected by reservation preview/create and automatic allocation (Task 4 test).
3. A stale request after switching stores must not show the previous store's map or seats (Task 5 test).
4. An image that fails to load, or a missing published map, must show a blocked state rather than the legacy 28-seat image (Task 5 test/manual check).
5. Replacing a published image must keep seat IDs and historical orders; disabling an old seat must prevent new bookings (Task 4 test).

## File Map

| File | Responsibility |
| --- | --- |
| `backend/app/models/__init__.py`, `backend/app/services/schema_migrate.py` | Store mode and versioned seat-map persistence; legacy-safe migration |
| `backend/app/services/store_seat_maps.py` | Draft/publish/restore invariants and per-store seat visibility |
| `backend/app/api/routes/admin_seat_maps.py`, `backend/app/main.py` | Admin image upload and map editing/publishing routes |
| `backend/app/api/routes/admin.py`, `backend/app/api/routes/admin_tools.py` | New-store closed default; image-mode seat management; no 28-seat backfill |
| `backend/app/api/routes/store.py`, `backend/app/services/booking.py`, `backend/app/services/business.py` | Public map/availability and server-side booking guard |
| `miniprogram/components/floor-plan-map/index.*`, `miniprogram/pages/store/seats.*` | Image-mode map with server-provided seat markers; legacy path retained |
| `admin-web/src/views/Seats.vue`, `admin-web/src/views/Stores.vue` | Per-store image-map editor and visible draft/closed states |
| `backend/tests/test_store_seat_maps.py`, `miniprogram/tests/seat-map.test.js` | Behavior tests |

---

### Task 1: Persist map modes and keep new stores closed

**Files:** Modify `backend/app/models/__init__.py`, `backend/app/services/schema_migrate.py`, `backend/app/api/routes/admin.py`, `admin-web/src/views/Stores.vue`; create `backend/tests/test_store_seat_maps.py`.

**Interfaces:** Produce `Store.seat_map_mode: str` (`legacy`/`image`) and `StoreSeatMap` with `id`, `store_id`, `version`, `state` (`draft`/`published`/`archived`), `image_path`, `aspect_ratio`, `markers` JSON, `created_at`, `published_at`. `markers` entries are `{seat_id: int, x_pct: float, y_pct: float, orient: 'h'|'v'}`. Keep `Store.floor_plan` as the published image path for compatibility.

- [ ] **Step 1: Write failing model tests.** In `test_store_seat_maps.py`, use an in-memory SQLite session and assert a legacy store still defaults to `legacy`, a new image-mode store can store a draft snapshot with markers, and `StoreSeatMap` rows survive commit/reload.
- [ ] **Step 2: Run `cd backend && python -m unittest discover -s tests -p test_store_seat_maps.py -v`.** Expect the new model tests to fail because `StoreSeatMap` and `seat_map_mode` do not exist.
- [ ] **Step 3: Add model fields and migration.** Add `stores.seat_map_mode VARCHAR(16) NOT NULL DEFAULT 'legacy'`; create `store_seat_maps` using the project's idempotent `schema_migrate.py` pattern. Restrict the automatic 28-seat backfill there to legacy stores. Existing rows read as legacy after migration.
- [ ] **Step 4: Change `create_store_admin` to create `seat_map_mode='image'`, `status=0`; make the Stores page show the new closed state.** Add a focused API test asserting the new store is absent from `/api/store/list`.
- [ ] **Step 5: Run the new backend tests and the existing admin build (`cd admin-web && npm run build`).** Expect all pass; inspect an existing-store database migration on a disposable copy for `seat_map_mode='legacy'` and no new seats in image-mode stores.
- [ ] **Step 6: Commit** model, migration, closed-store behavior, UI state, and tests as `feat: persist store seat map drafts`.

### Task 2: Draft, publish, and restore map snapshots

**Files:** Create `backend/app/services/store_seat_maps.py`; extend `backend/tests/test_store_seat_maps.py`.

**Interfaces:** Produce `get_draft_map(db: Session, store_id: int) -> StoreSeatMap | None`, `get_published_map(db: Session, store_id: int) -> StoreSeatMap | None`, `save_draft_map(db: Session, store_id: int, image_path: str, aspect_ratio: float, markers: list[dict]) -> StoreSeatMap`, `publish_draft_map(db: Session, store_id: int) -> StoreSeatMap`, `restore_map(db: Session, store_id: int, map_id: int) -> StoreSeatMap`, and `published_image_seat_ids(db: Session, store_id: int) -> set[int]`.

- [ ] **Step 1: Write failing service tests.** Assert a saved draft does not change the published row or `Store.floor_plan`; publication changes both in one transaction; restore creates a new published version from an earlier snapshot; repeated publication without a draft fails.
- [ ] **Step 2: Run the backend seat-map tests.** Expect failures for missing service functions.
- [ ] **Step 3: Implement service functions.** Validate positive finite aspect ratio; nonempty image and markers before publish; unique marker IDs, `0 <= x_pct,y_pct <= 100`, valid orientation, and every marker's `Seat.store_id`/`Zone.store_id` matching the target store. Lock the store row during publish; archive the old published row and commit the new snapshot and `Store.floor_plan` together.
- [ ] **Step 4: Add failure tests.** A cross-store seat, duplicate marker, bad coordinate, unknown seat, and empty draft each raise `ValueError` without changing published data. An unpublished new seat ID is absent from `published_image_seat_ids`.
- [ ] **Step 5: Run backend tests; expect pass. Commit** service and tests as `feat: publish versioned store seat maps`.

### Task 3: Expose secure admin map operations

**Files:** Create `backend/app/api/routes/admin_seat_maps.py`; modify `backend/app/main.py`, `backend/app/api/routes/admin_tools.py`, `backend/app/api/routes/admin.py`; extend `backend/tests/test_store_seat_maps.py`.

**Interfaces:** `GET /api/admin/stores/{store_id}/seat-map` returns draft/published summary; `POST .../seat-map/image` accepts one JPEG/PNG/WebP/GIF up to 2 MB and returns a server path; `PUT .../seat-map/draft` accepts `{image_path, aspect_ratio, markers}`; `POST .../seat-map/publish`; `POST .../seat-map/restore/{map_id}`. Add `GET/POST /api/admin/stores/{store_id}/zones` and `PATCH/DELETE /api/admin/stores/{store_id}/zones/{zone_id}`; deletion rejects zones containing seats. All require `get_current_admin`; writes call `log_admin_action`.

- [ ] **Step 1: Write failing FastAPI route tests** using an isolated SQLite session. Use a client without credentials for the 401 assertions, then an admin dependency override for valid draft/publish, malformed MIME/oversize image, cross-store marker or zone, legacy-store edit, and missing store/map assertions. Expect 400 for invalid input and 404 for absent resources. Zone deletion with seats returns 400.
- [ ] **Step 2: Run the route tests; expect missing-route failures.**
- [ ] **Step 3: Implement the router and register it in `main.py`.** Reuse the existing static upload path conventions, generate unique filenames, and return public image URLs without exposing filesystem paths. Add zone CRUD with store-ownership checks and audit entries for upload, save, publish, restore, and zone writes.
- [ ] **Step 4: In image mode, adjust existing admin seat create/edit/delete and summary routes to use that store's zones and seats without calling `ensure_store_seats`; keep the fixed-map backfill button limited to legacy mode.** Existing delete rule for a seat referenced by `Reservation` stays in force.
- [ ] **Step 5: Run route tests and a legacy admin-seats smoke test; expect pass. Commit** admin API and tests as `feat: manage store seat maps in admin API`.

### Task 4: Use published map seats in public and booking flows

**Files:** Modify `backend/app/api/routes/store.py`, `backend/app/api/routes/admin.py`, `backend/app/services/booking.py`, `backend/app/services/business.py`; extend `backend/tests/test_store_seat_maps.py`.

**Interfaces:** `GET /api/store/{store_id}/seat-map` returns `{mode, image_url, aspect_ratio, markers}` for published image mode and `{mode:'legacy'}` for legacy mode. For image mode, `published_image_seat_ids` defines all public, bookable, auto-allocation, admin booking, and change-seat candidate IDs. Legacy route behavior stays unchanged.

- [ ] **Step 1: Write failing tests.** Create valid pricing rules in the fixture so seat eligibility is what each test exercises. For a closed or unpublished image-mode store, `/store/list` and map/seat availability do not expose bookable seats, and preview/create reject its seat ID. After publication and opening in the test fixture, non-1–28 seats appear; unpublished, disabled, or cross-store seats fail preview/create and auto-allocation.
- [ ] **Step 2: Run backend tests; expect failures from fixed-code filtering and missing booking guard.**
- [ ] **Step 3: Update public routes and all booking entry points.** Add the map endpoint; branch existing `seats` and `availability` on mode; apply the published-ID guard in `validate_seat_for_booking`, `find_available_seat`, admin booking, and change-seat candidate generation. Fetch image-mode zone names from `Zone`, not `zone_name_by_slot`.
- [ ] **Step 4: Add tests for historical continuity.** Replacing a map retains `Reservation.seat_id`; disabling an old seat blocks a new booking but order detail still reports its original seat code. A legacy store still exposes its fixed numbered seats.
- [ ] **Step 5: Run all backend seat-map tests and existing booking smoke checks; expect pass. Commit** public and booking code as `feat: book seats from published store maps`.

### Task 5: Render per-store maps in the mini program

**Files:** Modify `miniprogram/pages/store/seats.js`, `.wxml`, `.wxss`, `miniprogram/components/floor-plan-map/index.js`, `.wxml`, `.wxss`; create `miniprogram/tests/seat-map.test.js`.

**Interfaces:** The seat page requests `/store/{storeId}/seat-map`; `mode='legacy'` uses `getLayout()` and existing room drawing; `mode='image'` renders the returned image and markers by seat ID, merged with `/availability` statuses. No image-mode marker is synthesized from `MAIN_POS`.

- [ ] **Step 1: Write failing Node tests** with stubbed page requests. Assert a 42-seat image map uses 42 markers/counts, store switching discards a late first-store response, missing map blocks selection, and legacy mode still uses `getLayout()`.
- [ ] **Step 2: Run `cd miniprogram && npm test`; expect the new tests to fail.**
- [ ] **Step 3: Add image-mode rendering and state handling.** Preserve zoom and tap behavior, derive labels/zones from server data, clear prior-store state before fetching, and show an explicit unavailable state on image failure or missing map; never fall back to the legacy drawing in image mode.
- [ ] **Step 4: Run `npm test`; expect pass.** In WeChat developer tools, visually check a portrait and landscape sample image at two viewport widths, zoom, tap, selected/busy/disabled markers, and image failure.
- [ ] **Step 5: Commit** mini-program changes and tests as `feat: render configurable store seat maps`.

### Task 6: Build the admin visual editor and release checks

**Files:** Modify `admin-web/src/views/Seats.vue`, `admin-web/src/views/Stores.vue`; create `admin-web/src/components/SeatMapEditor.vue` for the isolated canvas interaction.

**Interfaces:** The editor consumes Task 3 endpoints. Dragging writes 0–100% marker coordinates into local draft state; Save updates the draft; Publish is a separate explicit action. It shows store closed/open and draft/published status separately.

- [ ] **Step 1: Implement the editor component with upload/replace image, create/edit zones, add existing or new seat, position by click/drag, remove marker, zone/number fields, preview, save draft, publish, and restore previous version.** The image element supplies its natural aspect ratio; `pointer` coordinates are clamped to the canvas bounds.
- [ ] **Step 2: Restrict the old “补全标准座位” action to legacy mode and show the published map in read-only preview alongside draft state.** Disable Publish until image, at least one valid seat, and all markers are valid; publishing does not toggle store status.
- [ ] **Step 3: Run `cd admin-web && npm run build`; expect type check and build to pass.** Manually test upload, drag, save draft, public page remains on old layout, publish, restore, and switching between stores without stale map data.
- [ ] **Step 4: Run backend seat-map tests and `cd miniprogram && npm test`; expect pass.** Check `git diff` contains no edits to merchant credentials, customer balances, or existing order IDs.
- [ ] **Step 5: Commit** admin UI as `feat: edit and publish store seat maps`.

## Handoff After This Plan

Leave the sister's store closed. Prepare the separate payment/ownership plan covering her company merchant account, store-scoped admin access, balance/card/coupon isolation, price and hours configuration, refunds, and separate settlement reports. Opening the store is gated on that phase and real payment/refund verification.
