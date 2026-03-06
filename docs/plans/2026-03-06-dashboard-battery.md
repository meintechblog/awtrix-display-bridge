# Dashboard Battery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add battery status and a conservative external-power hint to dashboard display cards and display details.

**Architecture:** Extend runtime state from AWTRIX `/api/stats`, then surface the data in dashboard cards and the drawer. Only expose a subtle power hint when the data supports a conservative interpretation.

**Tech Stack:** Vue 3, Pinia, TypeScript, Vitest.

---

### Task 1: Add failing tests
- Modify `ui/src/stores/runtime.spec.ts`
- Modify `ui/src/components/displays/DisplayCard.spec.ts`
- Optionally modify `ui/src/components/displays/DisplayDrawer.spec.ts`
- Run targeted tests and confirm failure

### Task 2: Implement runtime battery fields
- Modify `ui/src/types/domain.ts`
- Modify `ui/src/stores/runtime.ts`
- Add battery parsing and conservative power hint derivation
- Re-run targeted tests

### Task 3: Render battery UI in dashboard
- Modify `ui/src/views/DashboardView.vue`
- Modify `ui/src/components/displays/DisplayCard.vue`
- Modify `ui/src/components/displays/DisplayDrawer.vue`
- Re-run targeted tests

### Task 4: Verify and deploy
- Run `npm --prefix ui run test -- --run`
- Run `npm --prefix ui run build`
- Merge to `main`, push, deploy to `192.168.3.163`

