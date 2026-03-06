<script setup lang="ts">
import { computed, ref } from 'vue';

import { buildLivePreviewUrl } from '../api/client';
import DisplayCard from '../components/displays/DisplayCard.vue';
import DisplayDrawer from '../components/displays/DisplayDrawer.vue';
import { useDisplayActions } from '../composables/useDisplayActions';
import { useRuntimeStore } from '../stores/runtime';
import { useWorkspaceStore } from '../stores/workspace';

const workspace = useWorkspaceStore();
const runtime = useRuntimeStore();
const actions = useDisplayActions();

const selectedDisplayId = ref<string | null>(null);

const cardModels = computed(() => workspace.displays.map((display) => {
  const assignedInputs = workspace.assignedInputs(display.id).map((input) => ({
    id: input.id,
    name: input.name,
    kind: input.kind,
  }));
  const state = runtime.displayStates[display.id];
  return {
    id: display.id,
    name: display.name,
    ip: display.ip,
    status: state?.state || 'unknown',
    previewUrl: buildLivePreviewUrl(display.ip),
    activeContent: assignedInputs[0]?.name || 'Keine aktiven Inputs',
    assignedInputs,
    version: state?.version,
    app: state?.app,
    wifiSignal: state?.wifiSignal,
    matrix: state?.matrix,
  };
}));

const selectedDisplay = computed(() => cardModels.value.find((display) => display.id === selectedDisplayId.value) || null);
const selectedAssignedInputs = computed(() => selectedDisplay.value ? selectedDisplay.value.assignedInputs : []);

async function clearSelected(displayId: string) {
  const display = workspace.displayById(displayId);
  if (!display) return;
  await actions.clearDisplay(display);
}

async function testSelected(displayId: string) {
  const display = workspace.displayById(displayId);
  if (!display) return;
  await actions.sendQuickTest(display);
}
</script>

<template>
  <section class="page-grid">
    <div class="section-head">
      <div>
        <p class="eyebrow">Dashboard</p>
        <h2>Displays im Betrieb</h2>
      </div>
    </div>

    <div class="card-grid">
      <DisplayCard
        v-for="display in cardModels"
        :key="display.id"
        :display="display"
        @open="selectedDisplayId = display.id"
        @clear="clearSelected(display.id)"
        @test-send="testSelected(display.id)"
      />
    </div>

    <DisplayDrawer
      :open="Boolean(selectedDisplay)"
      :display="selectedDisplay"
      :assigned-inputs="selectedAssignedInputs"
      @close="selectedDisplayId = null"
      @clear="selectedDisplayId && clearSelected(selectedDisplayId)"
      @test-send="selectedDisplayId && testSelected(selectedDisplayId)"
      @delete="selectedDisplayId && workspace.removeDisplay(selectedDisplayId)"
      @update-name="selectedDisplayId && workspace.updateDisplay(selectedDisplayId, { name: $event })"
      @update-ip="selectedDisplayId && workspace.updateDisplay(selectedDisplayId, { ip: $event })"
    />
  </section>
</template>
