<script setup lang="ts">
defineProps<{
  state: 'idle' | 'saving' | 'saved' | 'error';
  label: string;
  note?: string;
}>();
</script>

<template>
  <div class="save-badge" :data-state="state">
    <strong>{{ label }}</strong>
    <span>{{ note }}</span>
  </div>
</template>
