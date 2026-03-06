<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue';
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

function handleBeforeUnload(event: BeforeUnloadEvent) {
  if (!workspace.hasUnsavedChanges) {
    return;
  }
  event.preventDefault();
  event.returnValue = '';
}

function handleKeydown(event: KeyboardEvent) {
  const saveShortcut = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's';
  if (!saveShortcut) {
    return;
  }
  event.preventDefault();
  if (workspace.canSave) {
    void workspace.saveNow();
  }
}

onMounted(async () => {
  window.addEventListener('beforeunload', handleBeforeUnload);
  window.addEventListener('keydown', handleKeydown);
  if (!workspace.loaded && !workspace.loading) {
    await workspace.load();
  }
});

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload);
  window.removeEventListener('keydown', handleKeydown);
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

</script>

<template>
  <AppShell>
    <template #summary>
      <div class="summary-stack">
        <DashboardSummary :summary="summary" />
        <SaveStatusBadge :state="workspace.saveState" :label="workspace.saveLabel" :note="workspace.saveNote">
          <button type="button" class="ghost-btn" :disabled="!workspace.canDiscard" @click="workspace.discardChanges()">Verwerfen</button>
          <button type="button" class="primary-btn" :disabled="!workspace.canSave" @click="workspace.saveNow()">Speichern</button>
        </SaveStatusBadge>
      </div>
    </template>

    <main class="app-main">
      <RouterView />
    </main>
  </AppShell>
</template>
