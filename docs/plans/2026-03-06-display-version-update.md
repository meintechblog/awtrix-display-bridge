# Display Version and Update Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add per-display AWTRIX version status, server-side latest-version checks, and a best-effort update trigger to the `Displays` view.

**Architecture:** Extend the existing Python bridge with a small display-update helper and focused API endpoints, then consume that state from the Vue `Displays` view. Keep runtime/update semantics honest: comparison happens on the bridge, OTA triggering is exposed as a best-effort action only.

**Tech Stack:** Python 3, standard library HTTP/cache helpers, existing bridge HTTP server, Vue 3, Pinia, TypeScript, Vitest, unittest

---

### Task 1: Add backend tests for version status and update trigger

**Files:**
- Create: `tests/test_display_updates.py`
- Modify: `tests/test_app_api.py`

**Step 1: Write the failing test**

Add tests that verify:
- latest official version is fetched and cached
- current display version is read from `/api/stats`
- `update_available` is computed from server-side version comparison
- `POST /api/display/update` forwards the OTA trigger and returns the device result

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_display_updates tests.test_app_api.AppApiTests.test_display_update_status_returns_current_and_latest_versions -v`  
Expected: FAIL because the helper/API do not exist.

**Step 3: Write minimal implementation**

Implement a display-update helper and wire the endpoints into the bridge.

**Step 4: Run test to verify it passes**

Run the same command and confirm PASS.

**Step 5: Commit**

```bash
git add tests/test_display_updates.py tests/test_app_api.py bridge/display_updates.py bridge/mqtt_bridge.py
git commit -m "feat: add display version update api"
```

### Task 2: Add frontend tests and UI wiring

**Files:**
- Modify: `ui/src/views/DisplaysView.vue`
- Modify: `ui/src/views/DisplaysView.spec.ts`
- Modify: `ui/src/api/client.ts`
- Modify: `ui/src/types/domain.ts`
- Create: `ui/src/composables/useDisplayUpdates.ts`

**Step 1: Write the failing test**

Add a UI test that verifies a configured display shows:
- current version
- update badge when the latest version is newer
- `Update versuchen`
- `Webinterface`

**Step 2: Run test to verify it fails**

Run: `npm --prefix ui run test -- src/views/DisplaysView.spec.ts --run`  
Expected: FAIL because the UI does not render the new firmware state.

**Step 3: Write minimal implementation**

Implement the client calls, update composable, and display-card firmware actions.

**Step 4: Run test to verify it passes**

Run the same command and confirm PASS.

**Step 5: Commit**

```bash
git add ui/src/views/DisplaysView.vue ui/src/views/DisplaysView.spec.ts ui/src/api/client.ts ui/src/types/domain.ts ui/src/composables/useDisplayUpdates.ts
git commit -m "feat: add display version update ui"
```

### Task 3: Verify, deploy, and smoke-test

**Files:**
- Modify deployment targets only if needed

**Step 1: Run full backend verification**

Run: `python3 -m unittest discover -s tests -v`  
Expected: PASS.

**Step 2: Run full frontend verification**

Run: `npm --prefix ui run test -- --run && npm --prefix ui run build`  
Expected: PASS.

**Step 3: Deploy**

Deploy bridge and built UI to the Debian host, then restart the services.

**Step 4: Run live verification**

Verify:
- `GET /api/display/update-status?ip=192.168.3.126` returns current/latest version data
- `POST /api/display/update` returns a truthful OTA response
- the UI on `http://192.168.3.163` shows firmware status in `Displays`

**Step 5: Commit**

```bash
git add .
git commit -m "chore: deploy display version update feature"
```
