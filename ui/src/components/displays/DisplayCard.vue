<script setup lang="ts">
import StatusBadge from '../common/StatusBadge.vue';

defineProps<{
  display: {
    id: string;
    name: string;
    ip: string;
    status: string;
    previewUrl: string;
    activeContent: string;
    assignedInputs: Array<{ id: string; name: string; kind: string }>;
  };
}>();

defineEmits<{
  (event: 'open'): void;
  (event: 'clear'): void;
  (event: 'test-send'): void;
}>();
</script>

<template>
  <article class="display-card">
    <button type="button" class="card-hit" @click="$emit('open')">
      <header class="display-card-head">
        <div>
          <p class="eyebrow">Display</p>
          <h3>{{ display.name }}</h3>
          <span class="meta-copy">{{ display.ip }}</span>
        </div>
        <StatusBadge
          :label="display.status"
          :tone="display.status === 'online' ? 'ok' : display.status === 'offline' ? 'danger' : 'warn'"
        />
      </header>

      <iframe
        :src="display.previewUrl"
        title="Display preview"
        class="display-preview"
      />

      <div class="display-card-body">
        <p class="meta-copy">Aktiver Fokus</p>
        <strong>{{ display.activeContent }}</strong>
        <div class="tag-row">
          <span v-for="input in display.assignedInputs" :key="input.id" class="tag-pill">
            {{ input.name }}
          </span>
        </div>
      </div>
    </button>

    <footer class="card-actions">
      <button type="button" class="ghost-btn" @click="$emit('clear')">Clear</button>
      <button type="button" class="primary-btn" @click="$emit('test-send')">Test senden</button>
    </footer>
  </article>
</template>
