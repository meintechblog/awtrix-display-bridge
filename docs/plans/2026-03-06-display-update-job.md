# Display Update Job Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the long-running synchronous display update request with an async job model and a clearer update-check/status UX in the `Displays` view.

**Architecture:** The bridge keeps update execution server-side and exposes a short-lived in-memory job API. The Vue frontend triggers checks on page entry, starts async jobs for real updates, polls job state while running, and uses the same central CTA to represent both status and action.

**Tech Stack:** Python 3 bridge HTTP server, unittest, Vue 3, Pinia, Vitest, Vite.

---

### Task 1: Add backend failing tests for async update jobs

**Files:**
- Modify: `tests/test_display_updates.py`
- Test: `tests/test_display_updates.py`

**Step 1: Write the failing tests**

Add tests covering:
- `start_update_job(ip)` returns a job id and initial `checking` phase.
- A successful job progresses to `completed` with result payload.
- A failing job ends in `failed` with an error message.

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_display_updates.DisplayUpdateServiceTests -v`
Expected: FAIL because async job APIs do not exist.

**Step 3: Write minimal implementation**

Modify `bridge/display_updates.py` to add:
- in-memory job records
- worker-thread launch
- `start_update_job`
- `job_status`
- phase updates around the existing update flow

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_display_updates.DisplayUpdateServiceTests -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_display_updates.py bridge/display_updates.py
git commit -m "feat: add async display update jobs"
```

### Task 2: Add backend HTTP API tests for start/job endpoints

**Files:**
- Modify: `tests/test_app_api.py`
- Modify: `bridge/mqtt_bridge.py`
- Test: `tests/test_app_api.py`

**Step 1: Write the failing tests**

Add API tests covering:
- `POST /api/display/update/start` returns `job_id`
- `GET /api/display/update/job?id=...` returns job state
- invalid/missing ids return HTTP 400/404 with JSON error

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_app_api.AppApiTests -v`
Expected: FAIL with missing routes or wrong payload.

**Step 3: Write minimal implementation**

Modify `bridge/mqtt_bridge.py` to expose the new endpoints and map them to the update service.

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_app_api.AppApiTests -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_app_api.py bridge/mqtt_bridge.py
git commit -m "feat: expose display update job api"
```

### Task 3: Add frontend failing tests for initial check and async update states

**Files:**
- Modify: `ui/src/views/DisplaysView.spec.ts`
- Modify: `ui/src/api/client.ts`
- Modify: `ui/src/composables/useDisplayUpdates.ts`
- Modify: `ui/src/views/DisplaysView.vue`
- Test: `ui/src/views/DisplaysView.spec.ts`

**Step 1: Write the failing tests**

Add tests covering:
- initial firmware check happens on mount and shows `Update auf 0.98`
- clicking `Aktuell · 0.98` triggers a manual re-check
- clicking `Update auf 0.98` starts a job and then renders phase labels from polled job state
- no raw `Fetch is aborted` string is rendered

**Step 2: Run test to verify it fails**

Run: `npm --prefix ui run test -- ui/src/views/DisplaysView.spec.ts --run`
Expected: FAIL because client/composable/view do not support the new behavior.

**Step 3: Write minimal implementation**

Modify:
- `ui/src/api/client.ts` to add start/job API functions and remove the synchronous update call path from the view model.
- `ui/src/composables/useDisplayUpdates.ts` to manage one-time mount check, manual re-check, job polling, and phase mapping.
- `ui/src/views/DisplaysView.vue` to render `Update auf <latest>`, `Prüfe...`, running phases, and retry/current states.

**Step 4: Run test to verify it passes**

Run: `npm --prefix ui run test -- ui/src/views/DisplaysView.spec.ts --run`
Expected: PASS.

**Step 5: Commit**

```bash
git add ui/src/api/client.ts ui/src/composables/useDisplayUpdates.ts ui/src/views/DisplaysView.vue ui/src/views/DisplaysView.spec.ts
git commit -m "feat: improve display update ux"
```

### Task 4: Full verification and deployment

**Files:**
- Modify if needed: deployment files only if runtime wiring requires it

**Step 1: Run backend tests**

Run: `python3 -m unittest discover -s tests -v`
Expected: all tests pass.

**Step 2: Run frontend tests**

Run: `npm --prefix ui run test -- --run`
Expected: all tests pass.

**Step 3: Run production build**

Run: `npm --prefix ui run build`
Expected: successful build.

**Step 4: Deploy updated branch to the server workspace**

Sync the verified changes back to `/Users/hulki/projects/awtrix-display-bridge`, rebuild frontend, copy build output to the live web root, and restart the relevant systemd services on `192.168.3.163`.

**Step 5: Smoke-test the live endpoints**

Verify:
- `GET http://127.0.0.1:8090/api/display/update-status?ip=...`
- `POST http://127.0.0.1:8090/api/display/update/start`
- `GET http://127.0.0.1:8090/api/display/update/job?id=...`
- `http://127.0.0.1/displays`

**Step 6: Commit**

```bash
git add -A
git commit -m "chore: ship async display update flow"
```
