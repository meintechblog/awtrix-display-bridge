<script setup lang="ts">
defineProps<{
  displays: Array<{ id: string; name: string }>;
  selectedIds: string[];
}>();

defineEmits<{
  (event: 'toggle', displayId: string): void;
}>();
</script>

<template>
  <div class="binding-chips">
    <button
      v-for="display in displays"
      :key="display.id"
      type="button"
      class="tag-pill"
      :data-selected="selectedIds.includes(display.id)"
      @click="$emit('toggle', display.id)"
    >
      {{ display.name }}
    </button>
  </div>
</template>
