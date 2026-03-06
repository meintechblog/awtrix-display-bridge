<script setup lang="ts">
import StatusBadge from '../common/StatusBadge.vue';

defineProps<{
  input: {
    id: string;
    kind: string;
    name: string;
    assignedDisplayCount: number;
    sendMode?: string;
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
          <p class="eyebrow">{{ input.kind === 'mqtt' ? 'MQTT Skill' : input.kind === 'text' ? 'Text Skill' : `${input.kind} Skill` }}</p>
          <h3>{{ input.name }}</h3>
        </div>
        <StatusBadge
          :label="input.sendMode || 'off'"
          :tone="input.sendMode === 'realtime' ? 'ok' : input.sendMode && input.sendMode !== 'off' ? 'warn' : 'neutral'"
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
