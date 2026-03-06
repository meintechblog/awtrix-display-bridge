# Display Discovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Discover AWTRIX/Ulanzi displays continuously on the server's local private subnets and let users adopt them into the `Displays` page as unsaved drafts.

**Architecture:** Add an always-on server-side discovery worker inside the existing Python bridge, expose its cached state through a focused API, and consume it from the Vue `Displays` view. Keep persistence unchanged except that adoption flows through the existing explicit save/discard model.

**Tech Stack:** Python 3, standard library networking/threading, existing bridge HTTP server, Vue 3, Pinia, TypeScript, Vitest, unittest

---

### Task 1: Add backend discovery worker tests and service skeleton

**Files:**
- Create: `bridge/display_discovery.py`
- Create: `tests/test_display_discovery.py`

**Step 1: Write the failing test**

Create a unit test that verifies:
- local private subnets are derived from interface data
- already configured display IPs are excluded
- only successful AWTRIX-like probe results are returned
- the worker cache can be updated independently of any request

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_display_discovery -v`  
Expected: FAIL because `bridge.display_discovery` does not exist.

**Step 3: Write minimal implementation**

Implement a discovery service that:
- accepts injected interface/probe functions
- normalizes discovery items
- filters configured IPs

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_display_discovery -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add bridge/display_discovery.py tests/test_display_discovery.py
git commit -m "feat: add display discovery service"
```

### Task 2: Expose always-on discovery through the bridge API

**Files:**
- Modify: `bridge/mqtt_bridge.py`
- Test: `tests/test_app_api.py`

**Step 1: Write the failing test**

Add an API test for `GET /api/discovery/displays` that verifies:
- the endpoint returns cached results from the background worker
- configured display IPs are not returned
- normalized discovery results are serialized

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_app_api.AppApiTests.test_get_discovery_displays_returns_unconfigured_candidates -v`  
Expected: FAIL because the endpoint does not exist.

**Step 3: Write minimal implementation**

Wire the discovery service into the bridge and add:
- worker startup
- endpoint handler
- response serialization

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_app_api.AppApiTests.test_get_discovery_displays_returns_unconfigured_candidates -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add bridge/mqtt_bridge.py tests/test_app_api.py
git commit -m "feat: expose display discovery api"
```

### Task 3: Add frontend API client and discovery state

**Files:**
- Modify: `ui/src/api/client.ts`
- Modify: `ui/src/types/domain.ts`
- Create: `ui/src/composables/useDisplayDiscovery.ts`
- Test: `ui/src/stores/workspace.spec.ts`

**Step 1: Write the failing test**

Add a frontend test that verifies adopting a discovered display:
- adds a draft display to the workspace
- marks config state dirty
- does not persist immediately

**Step 2: Run test to verify it fails**

Run: `npm --prefix ui run test -- src/stores/workspace.spec.ts --run`  
Expected: FAIL because adoption helpers do not exist.

**Step 3: Write minimal implementation**

Implement:
- discovery API types/client calls
- adoption helper that inserts a draft display into workspace state
- dirty-state update

**Step 4: Run test to verify it passes**

Run: `npm --prefix ui run test -- src/stores/workspace.spec.ts --run`  
Expected: PASS.

**Step 5: Commit**

```bash
git add ui/src/api/client.ts ui/src/types/domain.ts ui/src/composables/useDisplayDiscovery.ts ui/src/stores/workspace.spec.ts
git commit -m "feat: add display discovery state handling"
```

### Task 4: Render passive discovery and adoption UI in Displays

**Files:**
- Modify: `ui/src/views/DisplaysView.vue`
- Modify: `ui/src/styles/base.css`
- Create: `ui/src/components/displays/DiscoveryCard.vue`
- Test: `ui/src/components/displays/DisplayCard.spec.ts`
- Test: `ui/src/App.spec.ts`

**Step 1: Write the failing test**

Add a UI test that verifies:
- the discovery section renders candidate displays
- clicking `Adoptieren` removes the candidate from discovery
- the adopted device appears in the configured display list only after insertion into workspace state

**Step 2: Run test to verify it fails**

Run: `npm --prefix ui run test -- src/App.spec.ts src/components/displays/DisplayCard.spec.ts --run`  
Expected: FAIL because discovery UI is missing.

**Step 3: Write minimal implementation**

Implement:
- discovery section above configured displays
- passive auto-refresh against cached discovery state
- adopt button
- loading/error/empty states

**Step 4: Run test to verify it passes**

Run: `npm --prefix ui run test -- src/App.spec.ts src/components/displays/DisplayCard.spec.ts --run`  
Expected: PASS.

**Step 5: Commit**

```bash
git add ui/src/views/DisplaysView.vue ui/src/components/displays/DiscoveryCard.vue ui/src/styles/base.css ui/src/App.spec.ts ui/src/components/displays/DisplayCard.spec.ts
git commit -m "feat: add display discovery adoption ui"
```

### Task 5: Verify, deploy, and smoke-test

**Files:**
- Modify: deployment targets only if required

**Step 1: Run full backend verification**

Run: `python3 -m unittest discover -s tests -v`  
Expected: PASS.

**Step 2: Run full frontend verification**

Run: `npm --prefix ui run test -- --run && npm --prefix ui run build`  
Expected: PASS.

**Step 3: Deploy**

Deploy updated bridge and built UI to the Debian server and restart the bridge service.

**Step 4: Run live verification**

Verify:
- `GET /api/discovery/displays` returns candidates or an empty valid payload
- configured displays are absent from discovery
- the built UI is served on `http://192.168.3.163`

**Step 5: Commit**

```bash
git add .
git commit -m "chore: deploy display discovery"
```
