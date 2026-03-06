<script setup lang="ts">
import StatusBadge from '../common/StatusBadge.vue';

defineProps<{
  input: {
    id: string;
    kind: string;
    name: string;
    assignedDisplayCount: number;
    autoMode?: string;
    preview?: string;
  };
}>();

defineEmits<{
  (event: 'open'): void;
  (event: 'delete'): void;
}>();
</script>

<template>
  <article class="input-card">
    <button type="button" class="card-hit" @click="$emit('open')">
      <header class="input-card-head">
        <div>
          <p class="eyebrow">{{ input.kind }}</p>
          <h3>{{ input.name }}</h3>
        </div>
        <StatusBadge
          :label="input.autoMode || input.kind"
          :tone="input.autoMode === 'realtime' ? 'ok' : input.autoMode && input.autoMode !== 'off' ? 'warn' : 'neutral'"
        />
      </header>

      <div class="input-card-body">
        <span class="meta-copy">{{ input.assignedDisplayCount }} Displays</span>
        <strong>{{ input.preview || '-' }}</strong>
      </div>
    </button>
    <footer class="card-actions">
      <button type="button" class="danger-btn" @click="$emit('delete')">Löschen</button>
    </footer>
  </article>
</template>
