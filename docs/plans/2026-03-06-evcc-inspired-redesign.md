# EVCC-Inspired Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild the current AWTRIX web app into a dashboard-first Vue/Vite application with EVCC-like UX while preserving the existing Python MQTT/AWTRIX runtime and browser-independent automation behavior.

**Architecture:** Keep `bridge/mqtt_bridge.py` as the runtime core, but extract a cleaner application API and persistence model around displays, inputs, bindings, and dashboard summaries. Build a parallel Vue 3 frontend in `ui/`, reach feature parity with the current single-file UI, then switch deployment to the compiled app while keeping the legacy frontend as fallback until cutover is stable.

**Tech Stack:** Python 3.11, `paho-mqtt`, Vue 3, Vite, TypeScript, Vue Router, Pinia, Vitest, Playwright

---

### Task 1: Scaffold the Vue/Vite app shell

**Files:**
- Create: `ui/package.json`
- Create: `ui/tsconfig.json`
- Create: `ui/vite.config.ts`
- Create: `ui/index.html`
- Create: `ui/src/main.ts`
- Create: `ui/src/App.vue`
- Create: `ui/src/router/index.ts`
- Create: `ui/src/stores/app.ts`
- Create: `ui/src/styles/tokens.css`
- Create: `ui/src/styles/base.css`
- Create: `ui/src/test/setup.ts`
- Test: `ui/src/App.spec.ts`

**Step 1: Write the failing test**

```ts
import { render, screen } from "@testing-library/vue";
import { createPinia } from "pinia";
import { createRouter, createMemoryHistory } from "vue-router";
import App from "./App.vue";

test("renders the primary navigation entries", async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { template: "<div>Dashboard</div>" } },
      { path: "/displays", component: { template: "<div>Displays</div>" } },
      { path: "/inputs", component: { template: "<div>Inputs</div>" } },
      { path: "/settings", component: { template: "<div>Settings</div>" } },
    ],
  });

  render(App, {
    global: {
      plugins: [createPinia(), router],
    },
  });

  expect(await screen.findByText("Dashboard")).toBeInTheDocument();
  expect(screen.getByText("Displays")).toBeInTheDocument();
  expect(screen.getByText("Inputs")).toBeInTheDocument();
  expect(screen.getByText("Settings")).toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix ui install && npm --prefix ui run test -- App.spec.ts`  
Expected: FAIL because the Vue app files do not exist yet.

**Step 3: Write minimal implementation**

```ts
// ui/src/main.ts
import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router";
import "./styles/tokens.css";
import "./styles/base.css";

createApp(App).use(createPinia()).use(router).mount("#app");
```

```vue
<!-- ui/src/App.vue -->
<template>
  <div class="app-shell">
    <nav class="primary-nav">
      <RouterLink to="/">Dashboard</RouterLink>
      <RouterLink to="/displays">Displays</RouterLink>
      <RouterLink to="/inputs">Inputs</RouterLink>
      <RouterLink to="/settings">Settings</RouterLink>
    </nav>
    <RouterView />
  </div>
</template>
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix ui run test -- App.spec.ts && npm --prefix ui run build`  
Expected: PASS and Vite build completes.

**Step 5: Commit**

```bash
git add ui
git commit -m "feat: scaffold vue dashboard app"
```

### Task 2: Extract persisted config models for displays, inputs, and bindings

**Files:**
- Create: `bridge/config_store.py`
- Modify: `bridge/mqtt_bridge.py`
- Test: `tests/test_config_store.py`

**Step 1: Write the failing test**

```python
import tempfile
import unittest

from bridge.config_store import ConfigStore


class ConfigStoreTests(unittest.TestCase):
    def test_persists_displays_inputs_and_bindings(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ConfigStore(f"{tmp}/app-config.json")
            store.replace_config(
                displays=[{"id": "d-1", "name": "Main", "ip": "192.168.3.126"}],
                inputs=[{"id": "i-1", "kind": "text", "name": "Status"}],
                bindings=[{"id": "b-1", "display_ids": ["d-1"], "input_id": "i-1"}],
            )

            loaded = store.load()

        self.assertEqual(loaded["displays"][0]["id"], "d-1")
        self.assertEqual(loaded["inputs"][0]["kind"], "text")
        self.assertEqual(loaded["bindings"][0]["input_id"], "i-1")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_config_store -v`  
Expected: FAIL with `ModuleNotFoundError` for `bridge.config_store`.

**Step 3: Write minimal implementation**

```python
import json
import os
import threading


class ConfigStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()

    def load(self):
        if not os.path.exists(self.path):
            return {"displays": [], "inputs": [], "bindings": []}
        with open(self.path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def replace_config(self, displays, inputs, bindings):
        payload = {
            "displays": list(displays),
            "inputs": list(inputs),
            "bindings": list(bindings),
        }
        with self._lock:
            with open(self.path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
```

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_config_store -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add bridge/config_store.py bridge/mqtt_bridge.py tests/test_config_store.py
git commit -m "feat: persist display input and binding config"
```

### Task 3: Add app API endpoints for displays, inputs, and bindings

**Files:**
- Create: `bridge/app_api.py`
- Modify: `bridge/mqtt_bridge.py`
- Test: `tests/test_app_api.py`

**Step 1: Write the failing test**

```python
import json
import tempfile
import unittest
from urllib import request

from bridge.mqtt_bridge import build_server


class AppApiTests(unittest.TestCase):
    def test_get_displays_returns_saved_display_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, thread = build_server("127.0.0.1", 0, config_path=f"{tmp}/app-config.json")
            try:
                bridge = server.bridge
                bridge.config_store.replace_config(
                    displays=[{"id": "d-1", "name": "Main", "ip": "192.168.3.126"}],
                    inputs=[],
                    bindings=[],
                )
                port = server.server_address[1]
                with request.urlopen(f"http://127.0.0.1:{port}/api/displays") as resp:
                    data = json.load(resp)
            finally:
                server.shutdown()
                thread.join(timeout=2)

        self.assertEqual(data["items"][0]["name"], "Main")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_app_api.AppApiTests.test_get_displays_returns_saved_display_records -v`  
Expected: FAIL because `build_server` or `/api/displays` does not exist yet.

**Step 3: Write minimal implementation**

```python
# bridge/app_api.py
def list_records(items):
    return {"items": list(items)}
```

```python
# inside bridge/mqtt_bridge.py
if parsed.path == "/api/displays":
    payload = self.server.bridge.config_store.load()
    return self._send_json(200, {"items": payload["displays"]})
```

Add matching handlers for:
- `GET /api/inputs`
- `GET /api/bindings`
- `PUT /api/config`

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_app_api -v`  
Expected: PASS for read and write API coverage.

**Step 5: Commit**

```bash
git add bridge/app_api.py bridge/mqtt_bridge.py tests/test_app_api.py
git commit -m "feat: add app config api endpoints"
```

### Task 4: Add dashboard summary and normalized runtime event payloads

**Files:**
- Create: `bridge/runtime_view.py`
- Modify: `bridge/mqtt_bridge.py`
- Test: `tests/test_runtime_view.py`

**Step 1: Write the failing test**

```python
import unittest

from bridge.runtime_view import build_dashboard_summary


class RuntimeViewTests(unittest.TestCase):
    def test_build_dashboard_summary_counts_online_and_offline_displays(self):
        config = {
            "displays": [
                {"id": "d-1", "name": "Main", "ip": "192.168.3.126"},
                {"id": "d-2", "name": "Aux", "ip": "192.168.3.127"},
            ]
        }
        runtime = {
            "display_status": {
                "d-1": {"state": "online"},
                "d-2": {"state": "offline"},
            }
        }

        summary = build_dashboard_summary(config, runtime)

        self.assertEqual(summary["totals"]["displays"], 2)
        self.assertEqual(summary["totals"]["online"], 1)
        self.assertEqual(summary["totals"]["offline"], 1)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_runtime_view -v`  
Expected: FAIL with `ModuleNotFoundError`.

**Step 3: Write minimal implementation**

```python
def build_dashboard_summary(config, runtime):
    displays = config.get("displays", [])
    status = runtime.get("display_status", {})
    online = sum(1 for item in displays if status.get(item["id"], {}).get("state") == "online")
    return {
        "totals": {
            "displays": len(displays),
            "online": online,
            "offline": len(displays) - online,
        }
    }
```

Also expose:
- `GET /api/dashboard`
- `GET /api/runtime/events`

Normalize runtime events so the frontend always receives:
- `type`
- `entity`
- `entity_id`
- `state`
- `updated_at_ms`
- `detail`

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_runtime_view -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add bridge/runtime_view.py bridge/mqtt_bridge.py tests/test_runtime_view.py
git commit -m "feat: add dashboard summary and runtime event api"
```

### Task 5: Add a hierarchical MQTT topic-browser API

**Files:**
- Create: `bridge/topic_browser.py`
- Modify: `bridge/mqtt_bridge.py`
- Test: `tests/test_topic_browser.py`

**Step 1: Write the failing test**

```python
import unittest

from bridge.topic_browser import list_children


class TopicBrowserTests(unittest.TestCase):
    def test_lists_only_next_level_children(self):
        topics = [
            "trading-deluxxe/webapp/status/balance",
            "trading-deluxxe/webapp/status/equity",
            "trading-deluxxe/webapp/orders/today",
        ]

        items = list_children(topics, "trading-deluxxe/webapp")

        self.assertEqual([item["segment"] for item in items], ["orders", "status"])
        self.assertTrue(all(item["kind"] == "branch" for item in items))
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_topic_browser -v`  
Expected: FAIL with `ModuleNotFoundError`.

**Step 3: Write minimal implementation**

```python
def list_children(topics, prefix):
    prefix = prefix.strip("/")
    needle = f"{prefix}/" if prefix else ""
    seen = set()
    items = []
    for topic in topics:
        if needle and not topic.startswith(needle):
            continue
        rest = topic[len(needle):]
        segment = rest.split("/", 1)[0]
        if not segment or segment in seen:
            continue
        seen.add(segment)
        items.append({"segment": segment, "kind": "branch" if "/" in rest else "leaf"})
    items.sort(key=lambda item: item["segment"])
    return items
```

Expose:
- `GET /api/topics/browser?broker_host=...&prefix=...&query=...`
- `GET /api/topics/value?broker_host=...&topic=...&json_key=...`

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_topic_browser -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add bridge/topic_browser.py bridge/mqtt_bridge.py tests/test_topic_browser.py
git commit -m "feat: add hierarchical mqtt topic browser api"
```

### Task 6: Build the EVCC-inspired app shell and design tokens

**Files:**
- Create: `ui/src/components/layout/AppShell.vue`
- Create: `ui/src/components/layout/AppHeader.vue`
- Create: `ui/src/components/layout/AppSidebar.vue`
- Create: `ui/src/views/DashboardView.vue`
- Create: `ui/src/views/DisplaysView.vue`
- Create: `ui/src/views/InputsView.vue`
- Create: `ui/src/views/SettingsView.vue`
- Modify: `ui/src/App.vue`
- Modify: `ui/src/router/index.ts`
- Modify: `ui/src/styles/tokens.css`
- Modify: `ui/src/styles/base.css`
- Test: `ui/src/components/layout/AppShell.spec.ts`

**Step 1: Write the failing test**

```ts
import { render, screen } from "@testing-library/vue";
import AppShell from "./AppShell.vue";

test("renders summary slot, navigation, and content shell", () => {
  render(AppShell, {
    slots: {
      summary: "<div>Summary</div>",
      default: "<div>Content</div>",
    },
  });

  expect(screen.getByText("Summary")).toBeInTheDocument();
  expect(screen.getByText("Content")).toBeInTheDocument();
  expect(screen.getByText("Dashboard")).toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix ui run test -- AppShell.spec.ts`  
Expected: FAIL because `AppShell.vue` does not exist yet.

**Step 3: Write minimal implementation**

```vue
<template>
  <div class="shell">
    <aside class="shell-sidebar">
      <RouterLink to="/">Dashboard</RouterLink>
      <RouterLink to="/displays">Displays</RouterLink>
      <RouterLink to="/inputs">Inputs</RouterLink>
      <RouterLink to="/settings">Settings</RouterLink>
    </aside>
    <main class="shell-main">
      <section class="shell-summary"><slot name="summary" /></section>
      <section class="shell-content"><slot /></section>
    </main>
  </div>
</template>
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix ui run test -- AppShell.spec.ts`  
Expected: PASS.

**Step 5: Commit**

```bash
git add ui/src/components/layout ui/src/views ui/src/App.vue ui/src/router/index.ts ui/src/styles
git commit -m "feat: add dashboard shell layout"
```

### Task 7: Implement dashboard summary cards and display cards

**Files:**
- Create: `ui/src/components/dashboard/DashboardSummary.vue`
- Create: `ui/src/components/displays/DisplayCard.vue`
- Create: `ui/src/stores/dashboard.ts`
- Create: `ui/src/stores/displays.ts`
- Create: `ui/src/api/client.ts`
- Modify: `ui/src/views/DashboardView.vue`
- Test: `ui/src/components/displays/DisplayCard.spec.ts`

**Step 1: Write the failing test**

```ts
import { render, screen } from "@testing-library/vue";
import DisplayCard from "./DisplayCard.vue";

test("shows display identity, status, preview, and quick actions", () => {
  render(DisplayCard, {
    props: {
      display: {
        id: "d-1",
        name: "Main Display",
        ip: "192.168.3.126",
        status: "online",
        previewUrl: "/live.html?display=192.168.3.126",
        activeContent: "Balance: 15568.91",
      },
    },
  });

  expect(screen.getByText("Main Display")).toBeInTheDocument();
  expect(screen.getByText("192.168.3.126")).toBeInTheDocument();
  expect(screen.getByText("online")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Clear" })).toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix ui run test -- DisplayCard.spec.ts`  
Expected: FAIL because `DisplayCard.vue` does not exist yet.

**Step 3: Write minimal implementation**

```vue
<template>
  <article class="display-card">
    <header>
      <h2>{{ display.name }}</h2>
      <p>{{ display.ip }}</p>
      <span>{{ display.status }}</span>
    </header>
    <iframe :src="display.previewUrl" title="Display preview" />
    <p>{{ display.activeContent }}</p>
    <div class="actions">
      <button type="button">Clear</button>
      <button type="button">Test senden</button>
    </div>
  </article>
</template>
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix ui run test -- DisplayCard.spec.ts`  
Expected: PASS.

**Step 5: Commit**

```bash
git add ui/src/components/dashboard ui/src/components/displays ui/src/stores ui/src/api ui/src/views/DashboardView.vue
git commit -m "feat: add dashboard summary and display cards"
```

### Task 8: Add display drawer, live preview controls, and quick actions

**Files:**
- Create: `ui/src/components/displays/DisplayDrawer.vue`
- Create: `ui/src/composables/useDisplayActions.ts`
- Modify: `ui/src/components/displays/DisplayCard.vue`
- Modify: `ui/src/stores/displays.ts`
- Test: `ui/src/components/displays/DisplayDrawer.spec.ts`

**Step 1: Write the failing test**

```ts
import { fireEvent, render, screen } from "@testing-library/vue";
import DisplayDrawer from "./DisplayDrawer.vue";

test("emits clear and test-send actions for the selected display", async () => {
  const { emitted } = render(DisplayDrawer, {
    props: {
      open: true,
      display: { id: "d-1", name: "Main", ip: "192.168.3.126" },
    },
  });

  await fireEvent.click(screen.getByRole("button", { name: "Clear" }));
  await fireEvent.click(screen.getByRole("button", { name: "Test senden" }));

  expect(emitted()["clear"]).toHaveLength(1);
  expect(emitted()["test-send"]).toHaveLength(1);
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix ui run test -- DisplayDrawer.spec.ts`  
Expected: FAIL because `DisplayDrawer.vue` does not exist yet.

**Step 3: Write minimal implementation**

```vue
<template>
  <aside v-if="open" class="display-drawer">
    <h2>{{ display.name }}</h2>
    <button type="button" @click="$emit('clear')">Clear</button>
    <button type="button" @click="$emit('test-send')">Test senden</button>
  </aside>
</template>
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix ui run test -- DisplayDrawer.spec.ts`  
Expected: PASS.

**Step 5: Commit**

```bash
git add ui/src/components/displays ui/src/composables ui/src/stores/displays.ts
git commit -m "feat: add display detail drawer and actions"
```

### Task 9: Build the reusable input library and binding UX

**Files:**
- Create: `ui/src/components/inputs/InputCard.vue`
- Create: `ui/src/components/inputs/TextInputEditor.vue`
- Create: `ui/src/components/inputs/MqttInputEditor.vue`
- Create: `ui/src/components/inputs/BindingChips.vue`
- Create: `ui/src/stores/inputs.ts`
- Create: `ui/src/stores/bindings.ts`
- Modify: `ui/src/views/InputsView.vue`
- Test: `ui/src/components/inputs/InputCard.spec.ts`

**Step 1: Write the failing test**

```ts
import { render, screen } from "@testing-library/vue";
import InputCard from "./InputCard.vue";

test("renders reusable input metadata and assigned display count", () => {
  render(InputCard, {
    props: {
      input: {
        id: "i-1",
        kind: "mqtt",
        name: "Balance Feed",
        assignedDisplayCount: 2,
        autoMode: "realtime",
      },
    },
  });

  expect(screen.getByText("Balance Feed")).toBeInTheDocument();
  expect(screen.getByText("mqtt")).toBeInTheDocument();
  expect(screen.getByText("2 Displays")).toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix ui run test -- InputCard.spec.ts`  
Expected: FAIL because the input components do not exist yet.

**Step 3: Write minimal implementation**

```vue
<template>
  <article class="input-card">
    <h3>{{ input.name }}</h3>
    <p>{{ input.kind }}</p>
    <span>{{ input.assignedDisplayCount }} Displays</span>
    <span>{{ input.autoMode }}</span>
  </article>
</template>
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix ui run test -- InputCard.spec.ts`  
Expected: PASS.

**Step 5: Commit**

```bash
git add ui/src/components/inputs ui/src/stores/inputs.ts ui/src/stores/bindings.ts ui/src/views/InputsView.vue
git commit -m "feat: add reusable input library ui"
```

### Task 10: Build the hierarchical MQTT topic browser UI

**Files:**
- Create: `ui/src/components/mqtt/TopicBrowser.vue`
- Create: `ui/src/components/mqtt/TopicPathBar.vue`
- Create: `ui/src/composables/useTopicBrowser.ts`
- Modify: `ui/src/components/inputs/MqttInputEditor.vue`
- Test: `ui/src/components/mqtt/TopicBrowser.spec.ts`

**Step 1: Write the failing test**

```ts
import { fireEvent, render, screen } from "@testing-library/vue";
import TopicBrowser from "./TopicBrowser.vue";

test("drills down one level at a time and emits a selected leaf topic", async () => {
  const { emitted } = render(TopicBrowser, {
    props: {
      items: [
        { segment: "trading-deluxxe", kind: "branch", path: "trading-deluxxe" },
        { segment: "other", kind: "branch", path: "other" },
      ],
    },
  });

  await fireEvent.click(screen.getByText("trading-deluxxe"));

  expect(emitted()["navigate"]).toHaveLength(1);
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix ui run test -- TopicBrowser.spec.ts`  
Expected: FAIL because `TopicBrowser.vue` does not exist yet.

**Step 3: Write minimal implementation**

```vue
<template>
  <ul class="topic-browser">
    <li v-for="item in items" :key="item.path">
      <button type="button" @click="$emit(item.kind === 'leaf' ? 'select' : 'navigate', item)">
        {{ item.segment }}
      </button>
    </li>
  </ul>
</template>
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix ui run test -- TopicBrowser.spec.ts`  
Expected: PASS.

**Step 5: Commit**

```bash
git add ui/src/components/mqtt ui/src/composables/useTopicBrowser.ts ui/src/components/inputs/MqttInputEditor.vue
git commit -m "feat: add mqtt topic browser ui"
```

### Task 11: Wire autosave, runtime SSE, and stale-state handling

**Files:**
- Create: `ui/src/composables/useRuntimeStream.ts`
- Create: `ui/src/stores/runtime.ts`
- Create: `ui/src/components/common/SaveStatusBadge.vue`
- Modify: `ui/src/stores/displays.ts`
- Modify: `ui/src/stores/inputs.ts`
- Modify: `ui/src/stores/bindings.ts`
- Modify: `ui/src/views/DashboardView.vue`
- Test: `ui/src/stores/runtime.spec.ts`

**Step 1: Write the failing test**

```ts
import { createPinia, setActivePinia } from "pinia";
import { useRuntimeStore } from "./runtime";

test("marks a display as stale when no runtime event arrives within threshold", () => {
  setActivePinia(createPinia());
  const store = useRuntimeStore();

  store.upsertEvent({
    type: "display-status",
    entity: "display",
    entity_id: "d-1",
    state: "online",
    updated_at_ms: 1000,
    detail: {},
  });

  store.markStaleAt(9000, 5000);

  expect(store.byId["d-1"].state).toBe("stale");
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix ui run test -- runtime.spec.ts`  
Expected: FAIL because the runtime store does not exist yet.

**Step 3: Write minimal implementation**

```ts
import { defineStore } from "pinia";

export const useRuntimeStore = defineStore("runtime", {
  state: () => ({
    byId: {} as Record<string, { state: string; updatedAtMs: number }>,
  }),
  actions: {
    upsertEvent(event: { entity_id: string; state: string; updated_at_ms: number }) {
      this.byId[event.entity_id] = {
        state: event.state,
        updatedAtMs: event.updated_at_ms,
      };
    },
    markStaleAt(nowMs: number, staleThresholdMs: number) {
      Object.values(this.byId).forEach((item) => {
        if (nowMs - item.updatedAtMs > staleThresholdMs) item.state = "stale";
      });
    },
  },
});
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix ui run test -- runtime.spec.ts`  
Expected: PASS.

**Step 5: Commit**

```bash
git add ui/src/composables/useRuntimeStream.ts ui/src/stores/runtime.ts ui/src/components/common/SaveStatusBadge.vue ui/src/stores ui/src/views/DashboardView.vue
git commit -m "feat: wire runtime stream and save state"
```

### Task 12: Add end-to-end verification, deployment updates, and cutover docs

**Files:**
- Create: `ui/playwright.config.ts`
- Create: `ui/tests/e2e/dashboard.spec.ts`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`
- Modify: `deploy/systemd/ulanzi-mqtt-bridge.service`

**Step 1: Write the failing test**

```ts
import { test, expect } from "@playwright/test";

test("dashboard shows displays and opens input workflow", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Dashboard")).toBeVisible();
  await expect(page.getByText("Displays")).toBeVisible();
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix ui run test:e2e -- dashboard.spec.ts`  
Expected: FAIL because Playwright config and served app are not ready yet.

**Step 3: Write minimal implementation**

```yaml
# .github/workflows/ci.yml
- name: Install UI dependencies
  run: npm --prefix ui ci

- name: Run UI unit tests
  run: npm --prefix ui run test -- --run

- name: Build UI
  run: npm --prefix ui run build

- name: Run bridge tests
  run: python3 -m unittest -v
```

Document:
- local UI dev workflow
- production build + copy to `/var/www/ulanzi`
- legacy UI fallback path
- rollback steps

**Step 4: Run test to verify it passes**

Run: `npm --prefix ui run test:e2e -- dashboard.spec.ts && npm --prefix ui run build && python3 -m unittest -v`  
Expected: PASS for E2E smoke, UI build, and backend tests.

**Step 5: Commit**

```bash
git add ui/playwright.config.ts ui/tests/e2e .github/workflows/ci.yml README.md CONTRIBUTING.md deploy/systemd/ulanzi-mqtt-bridge.service
git commit -m "chore: add ui verification and deployment docs"
```

## Migration Notes

- Keep `frontend/index.html` and `frontend/live.html` untouched until the Vue app has feature parity.
- Route the deployed static root to `ui/dist` only after Task 12 passes.
- Preserve the current browser-independent auto-routing behavior throughout all tasks.
- Do not merge the Vue cutover until manual verification passes on the Debian host and the AWTRIX display.

## Verification Checklist

- `python3 -m unittest -v`
- `npm --prefix ui run test -- --run`
- `npm --prefix ui run build`
- `npm --prefix ui run test:e2e`
- manual check on `192.168.3.163`
- manual AWTRIX send, clear, preview, MQTT realtime, MQTT interval, topic-browser drilldown
