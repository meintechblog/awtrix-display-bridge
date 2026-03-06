<script setup lang="ts">
import { computed } from 'vue';

import { buildLivePreviewUrl } from '../api/client';
import StatusBadge from '../components/common/StatusBadge.vue';
import { useWorkspaceStore } from '../stores/workspace';
import { useRuntimeStore } from '../stores/runtime';

const workspace = useWorkspaceStore();
const runtime = useRuntimeStore();

const displays = computed(() => workspace.displays.map((display) => ({
  ...display,
  previewUrl: buildLivePreviewUrl(display.ip),
  status: runtime.displayStates[display.id]?.state || 'unknown',
})));
</script>

<template>
  <section class="page-grid">
    <div class="section-head">
      <div>
        <p class="eyebrow">Displays</p>
        <h2>Display-Konfiguration</h2>
      </div>
      <button type="button" class="primary-btn" @click="workspace.addDisplay()">Display hinzufügen</button>
    </div>

    <article v-for="display in displays" :key="display.id" class="config-card">
      <div class="field-grid two">
        <div class="field-stack">
          <label>Name</label>
          <input :value="display.name" @input="workspace.updateDisplay(display.id, { name: ($event.target as HTMLInputElement).value })" />
        </div>
        <div class="field-stack">
          <label>IP</label>
          <input :value="display.ip" @input="workspace.updateDisplay(display.id, { ip: ($event.target as HTMLInputElement).value })" />
        </div>
      </div>

      <div class="tag-row">
        <StatusBadge :label="display.status" :tone="display.status === 'online' ? 'ok' : display.status === 'offline' ? 'danger' : 'warn'" />
        <button type="button" class="danger-btn" :disabled="workspace.displays.length <= 1" @click="workspace.removeDisplay(display.id)">Löschen</button>
      </div>

      <iframe :src="display.previewUrl" title="Display preview" class="display-preview config-preview" />
    </article>
  </section>
</template>
