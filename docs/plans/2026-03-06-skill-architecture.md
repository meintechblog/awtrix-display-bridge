# Skill Architecture Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reframe the project as a modular skill-based AWTRIX bridge, separate skill-specific config from generic delivery policy, and make the repository contributor-friendly for new built-in skills.

**Architecture:** Keep runtime compatibility by migrating the existing `text` and `mqtt` input records into a new skill model in-place. Introduce shared delivery config fields, update the Vue UI from `Inputs` to `Skills`, and refactor bridge auto-route generation to use normalized skill + delivery policy instead of MQTT-specific display config.

**Tech Stack:** Python 3 bridge, Vue 3, Pinia, TypeScript, unittest, Vitest.

---

### Task 1: Add failing tests for skill model normalization and route generation

**Files:**
- Modify: `ui/src/stores/workspace.spec.ts`
- Modify: `tests/test_config_store.py`
- Modify: `tests/test_mqtt_bridge.py`

**Step 1: Write the failing tests**
Add tests for:
- legacy `text` and `mqtt` records loading into a new skill/delivery shape
- generic delivery fields surviving save/load
- bridge route generation reading generic delivery config instead of MQTT-only fields

**Step 2: Run tests to verify failure**
Run:
- `python3 -m unittest tests.test_config_store tests.test_mqtt_bridge -v`
- `npm --prefix ui run test -- src/stores/workspace.spec.ts --run`
Expected: FAIL due to missing generic delivery shape.

**Step 3: Write minimal implementation**
Modify workspace/config/runtime normalization functions and bridge route generation.

**Step 4: Re-run tests**
Expected: PASS.

**Step 5: Commit**
```bash
git add tests/test_config_store.py tests/test_mqtt_bridge.py ui/src/stores/workspace.spec.ts bridge/config_store.py bridge/mqtt_bridge.py ui/src/stores/workspace.ts ui/src/types/domain.ts ui/src/utils/defaults.ts
git commit -m "refactor: add skill and delivery config model"
```

### Task 2: Rename product surface from Inputs to Skills and update editors/cards

**Files:**
- Modify: `ui/src/views/InputsView.vue`
- Modify: `ui/src/router/index.ts`
- Modify: `ui/src/components/layout/AppSidebar.vue`
- Modify: `ui/src/components/inputs/InputCard.vue`
- Modify: `ui/src/components/inputs/TextInputEditor.vue`
- Modify: `ui/src/components/inputs/MqttInputEditor.vue`
- Modify: `ui/src/App.vue`
- Modify tests as needed

**Step 1: Write the failing tests**
Add/update tests to expect `Skills` naming and cards/editors using skill terminology.

**Step 2: Run tests to verify failure**
Run the relevant Vitest files.

**Step 3: Write minimal implementation**
Update labels, metadata, shared delivery UI, and route naming while preserving current behavior.

**Step 4: Re-run tests**
Expected: PASS.

**Step 5: Commit**
```bash
git add ui/src/views/InputsView.vue ui/src/router/index.ts ui/src/components/layout/AppSidebar.vue ui/src/components/inputs/InputCard.vue ui/src/components/inputs/TextInputEditor.vue ui/src/components/inputs/MqttInputEditor.vue ui/src/App.vue ui/src/**/*.spec.ts
git commit -m "feat: present built-in skills in ui"
```

### Task 3: Add visible repo-level skill contribution structure and docs

**Files:**
- Modify: `README.md`
- Create: `skills/README.md`
- Create: `skills/text/README.md`
- Create: `skills/mqtt/README.md`

**Step 1: Write/update docs**
Document:
- project as skill-based bridge
- built-in skills
- generic delivery layer
- how contributors add a new built-in skill by PR

**Step 2: Sanity-check docs for consistency**
Use quick grep/read pass to ensure old top-level wording does not contradict the new model.

**Step 3: Commit**
```bash
git add README.md skills/README.md skills/text/README.md skills/mqtt/README.md
git commit -m "docs: document built-in skill system"
```

### Task 4: Full verification, merge, deploy

**Step 1: Run backend suite**
`python3 -m unittest discover -s tests -v`

**Step 2: Run frontend suite**
`npm --prefix ui run test -- --run`

**Step 3: Build frontend**
`npm --prefix ui run build`

**Step 4: Merge branch to `main`, push, deploy to `192.168.3.163`**
Deploy updated bridge code, built frontend, and docs.

**Step 5: Smoke test live UI and bridge**
Verify:
- `/skills` or renamed skill navigation path if changed
- `/displays`
- server route generation still works

