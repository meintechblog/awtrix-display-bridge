<script setup lang="ts">
defineProps<{
  breadcrumb: Array<{ label: string; path: string }>;
}>();

defineEmits<{
  (event: 'jump', path: string): void;
}>();
</script>

<template>
  <div class="topic-path">
    <button type="button" class="ghost-btn" @click="$emit('jump', '')">Root</button>
    <button
      v-for="crumb in breadcrumb"
      :key="crumb.path"
      type="button"
      class="ghost-btn"
      @click="$emit('jump', crumb.path)"
    >
      {{ crumb.label }}
    </button>
  </div>
</template>
