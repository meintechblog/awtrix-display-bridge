<script setup lang="ts">
defineProps<{
  state: 'idle' | 'dirty' | 'saving' | 'saved' | 'error';
  label: string;
  note?: string;
}>();
</script>

<template>
  <div class="save-badge" :data-state="state">
    <div class="save-badge-copy">
      <strong>{{ label }}</strong>
      <span>{{ note }}</span>
    </div>
    <div v-if="$slots.default" class="save-badge-actions">
      <slot />
    </div>
  </div>
</template>
