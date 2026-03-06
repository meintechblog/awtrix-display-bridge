<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { RouterView } from 'vue-router';

import SaveStatusBadge from './components/common/SaveStatusBadge.vue';
import DashboardSummary from './components/dashboard/DashboardSummary.vue';
import AppShell from './components/layout/AppShell.vue';
import { useRuntimeStream } from './composables/useRuntimeStream';
import { useRuntimeStore } from './stores/runtime';
import { useWorkspaceStore } from './stores/workspace';

const workspace = useWorkspaceStore();
const runtime = useRuntimeStore();

useRuntimeStream();

onMounted(async () => {
  if (!workspace.loaded && !workspace.loading) {
    await workspace.load();
  }
});

const summary = computed(() => {
  const states = workspace.displays.map((display) => runtime.displayStates[display.id]?.state || 'unknown');
  return {
    displays: workspace.displays.length,
    online: states.filter((state) => state === 'online').length,
    offline: states.filter((state) => state === 'offline').length,
    stale: states.filter((state) => state === 'stale' || state === 'unknown').length,
    inputs: workspace.inputs.length,
    bindings: workspace.bindings.length,
    liveBrokers: runtime.connectedBrokerCount,
  };
});

const saveNote = computed(() => {
  if (workspace.saveState === 'error') {
    return workspace.saveError || 'Speichern fehlgeschlagen.';
  }
  if (workspace.lastSavedAt > 0) {
    return `Letzte Speicherung ${new Date(workspace.lastSavedAt).toLocaleTimeString('de-DE')}`;
  }
  return 'Konfig-Änderungen werden automatisch gespeichert.';
});
</script>

<template>
  <AppShell>
    <template #summary>
      <div class="summary-stack">
        <DashboardSummary :summary="summary" />
        <SaveStatusBadge :state="workspace.saveState" :label="workspace.saveLabel" :note="saveNote" />
      </div>
    </template>

    <main class="app-main">
      <RouterView />
    </main>
  </AppShell>
</template>
