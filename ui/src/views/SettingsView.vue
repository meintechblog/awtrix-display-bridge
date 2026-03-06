<script setup lang="ts">
import { computed } from 'vue';

import SaveStatusBadge from '../components/common/SaveStatusBadge.vue';
import StatusBadge from '../components/common/StatusBadge.vue';
import { useRuntimeStore } from '../stores/runtime';
import { useWorkspaceStore } from '../stores/workspace';

const workspace = useWorkspaceStore();
const runtime = useRuntimeStore();

const bridgeUrl = computed(() => `${window.location.protocol}//${window.location.hostname}:8090`);
</script>

<template>
  <section class="page-grid">
    <div class="section-head">
      <div>
        <p class="eyebrow">Settings</p>
        <h2>Systemstatus</h2>
      </div>
    </div>

    <article class="config-card">
      <p class="eyebrow">Bridge</p>
      <strong>{{ bridgeUrl }}</strong>
      <div class="tag-row">
        <StatusBadge label="MQTT Runtime" :tone="runtime.connectedBrokerCount > 0 ? 'ok' : 'warn'" />
        <StatusBadge :label="`${runtime.connectedBrokerCount} Broker live`" tone="neutral" />
      </div>
    </article>

    <SaveStatusBadge :state="workspace.saveState" :label="workspace.saveLabel" :note="workspace.saveNote">
      <button type="button" class="ghost-btn" :disabled="!workspace.canDiscard" @click="workspace.discardChanges()">Verwerfen</button>
      <button type="button" class="primary-btn" :disabled="!workspace.canSave" @click="workspace.saveNow()">Speichern</button>
    </SaveStatusBadge>
  </section>
</template>
