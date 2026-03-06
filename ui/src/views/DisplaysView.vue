<script setup lang="ts">
import { computed } from 'vue';

import { buildLivePreviewUrl } from '../api/client';
import DiscoveryCard from '../components/displays/DiscoveryCard.vue';
import SaveStatusBadge from '../components/common/SaveStatusBadge.vue';
import StatusBadge from '../components/common/StatusBadge.vue';
import { useDisplayDiscovery } from '../composables/useDisplayDiscovery';
import { useWorkspaceStore } from '../stores/workspace';
import { useRuntimeStore } from '../stores/runtime';

const workspace = useWorkspaceStore();
const runtime = useRuntimeStore();
const {
  items: discoveredDisplays,
  loading: discoveryLoading,
  error: discoveryError,
  lastUpdatedAtMs: discoveryUpdatedAtMs,
  scanActive: discoveryScanActive,
} = useDisplayDiscovery(() => workspace.displays.map((display) => display.ip));

const displays = computed(() => workspace.displays.map((display) => ({
  ...display,
  previewUrl: buildLivePreviewUrl(display.ip),
  status: runtime.displayStates[display.id]?.state || 'unknown',
})));

const discoveryNote = computed(() => {
  if (discoveryError.value) {
    return discoveryError.value;
  }
  if (discoveryLoading.value && !discoveredDisplays.value.length) {
    return 'Scannt lokale Netzwerke...';
  }
  if (discoveryScanActive.value) {
    return 'Netzscan läuft im Hintergrund.';
  }
  if (discoveryUpdatedAtMs.value > 0) {
    return `Letzter Netzscan ${new Date(discoveryUpdatedAtMs.value).toLocaleTimeString('de-DE')}`;
  }
  return 'Discovery ist aktiv.';
});
</script>

<template>
  <section class="page-grid">
    <div class="section-head">
      <div>
        <p class="eyebrow">Displays</p>
        <h2>Display-Konfiguration</h2>
      </div>
      <button type="button" class="ghost-btn" @click="workspace.addDisplay()">Manuell hinzufügen</button>
    </div>

    <SaveStatusBadge :state="workspace.saveState" :label="workspace.saveLabel" :note="workspace.saveNote">
      <button type="button" class="ghost-btn" :disabled="!workspace.canDiscard" @click="workspace.discardChanges()">Verwerfen</button>
      <button type="button" class="primary-btn" :disabled="!workspace.canSave" @click="workspace.saveNow()">Speichern</button>
    </SaveStatusBadge>

    <article class="config-card">
      <div class="section-head">
        <div>
          <p class="eyebrow">Discovery</p>
          <h3>Verfügbare Displays</h3>
        </div>
        <span class="meta-copy">{{ discoveryNote }}</span>
      </div>

      <div v-if="discoveredDisplays.length" class="card-grid compact">
        <DiscoveryCard
          v-for="item in discoveredDisplays"
          :key="item.ip"
          :item="item"
          @adopt="workspace.adoptDiscoveredDisplay(item)"
        />
      </div>
      <p v-else class="meta-copy">Keine neuen Displays gefunden.</p>
    </article>

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
