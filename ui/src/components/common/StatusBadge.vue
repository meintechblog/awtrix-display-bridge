<script setup lang="ts">
defineProps<{
  label: string;
  tone?: 'neutral' | 'ok' | 'warn' | 'danger';
}>();
</script>

<template>
  <span class="status-badge" :data-tone="tone || 'neutral'">{{ label }}</span>
</template>
