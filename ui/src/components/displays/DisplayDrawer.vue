<script setup lang="ts">
import StatusBadge from '../common/StatusBadge.vue';

defineProps<{
  open: boolean;
  display: {
    id: string;
    name: string;
    ip: string;
    status: string;
    version?: string;
    app?: string;
    wifiSignal?: number | null;
    matrix?: boolean | null;
    batteryLevel?: number | null;
    externalPowerHint?: boolean;
    previewUrl?: string;
  } | null;
  assignedInputs: Array<{ id: string; name: string; kind: string }>;
}>();

defineEmits<{
  (event: 'close'): void;
  (event: 'clear'): void;
  (event: 'test-send'): void;
  (event: 'delete'): void;
  (event: 'update-name', value: string): void;
  (event: 'update-ip', value: string): void;
}>();
</script>

<template>
  <aside v-if="open && display" class="drawer">
    <div class="drawer-head">
      <div>
        <p class="eyebrow">Display Details</p>
        <h2>{{ display.name }}</h2>
      </div>
      <button type="button" class="ghost-btn" @click="$emit('close')">Schließen</button>
    </div>

    <div class="drawer-grid">
      <div class="field-stack">
        <label>Name</label>
        <input :value="display.name" @input="$emit('update-name', ($event.target as HTMLInputElement).value)" />
      </div>
      <div class="field-stack">
        <label>IP</label>
        <input :value="display.ip" @input="$emit('update-ip', ($event.target as HTMLInputElement).value)" />
      </div>
    </div>

    <div class="tag-row">
      <StatusBadge
        :label="display.status"
        :tone="display.status === 'online' ? 'ok' : display.status === 'offline' ? 'danger' : 'warn'"
      />
      <span class="tag-pill">Version {{ display.version || '-' }}</span>
      <span class="tag-pill">App {{ display.app || '-' }}</span>
      <span class="tag-pill">Signal {{ display.wifiSignal ?? '-' }}</span>
      <span class="tag-pill">Matrix {{ display.matrix ? 'an' : 'aus' }}</span>
      <span v-if="typeof display.batteryLevel === 'number'" class="tag-pill">Akku {{ display.batteryLevel }}%</span>
      <span v-if="display.externalPowerHint" class="tag-pill">Strom an</span>
    </div>

    <iframe
      v-if="display.previewUrl"
      :src="display.previewUrl"
      title="Display preview"
      class="display-preview drawer-preview"
    />

    <div class="drawer-section">
      <p class="eyebrow">Zugeordnete Skills</p>
      <div class="tag-row">
        <span v-for="input in assignedInputs" :key="input.id" class="tag-pill">{{ input.name }}</span>
        <span v-if="!assignedInputs.length" class="meta-copy">Keine Skills zugeordnet.</span>
      </div>
    </div>

    <div class="card-actions">
      <button type="button" class="ghost-btn" @click="$emit('clear')">Clear</button>
      <button type="button" class="primary-btn" @click="$emit('test-send')">Test senden</button>
      <button type="button" class="danger-btn" @click="$emit('delete')">Display löschen</button>
    </div>
  </aside>
</template>
