# Update CTA Consolidation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the separate firmware update status elements with one compact stateful CTA in the display card.

**Architecture:** Keep the existing firmware data flow intact and only reshape the display-card rendering logic and tests. One passive current-version pill remains; the latest-version and update-action elements collapse into a single CTA/badge state machine.

**Tech Stack:** Vue 3, TypeScript, Vitest

---

### Task 1: Update UI regression test

**Files:**
- Modify: `ui/src/views/DisplaysView.spec.ts`

**Step 1: Write the failing test**

Assert that the display row shows:
- `Version <current>`
- one clickable CTA `Update verfügbar · <latest>`
- no separate `Neueste <latest>` pill
- no separate passive `Update verfügbar` badge

**Step 2: Run test to verify it fails**

Run: `npm --prefix ui run test -- src/views/DisplaysView.spec.ts --run`
Expected: FAIL because the old three-element layout still renders.

**Step 3: Write minimal implementation**

Collapse the current update row into one stateful CTA.

**Step 4: Run test to verify it passes**

Run the same command and confirm PASS.

**Step 5: Commit**

```bash
git add ui/src/views/DisplaysView.spec.ts ui/src/views/DisplaysView.vue ui/src/styles/base.css
git commit -m "feat: consolidate display update cta"
```
