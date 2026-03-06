<script setup lang="ts">
import TopicPathBar from './TopicPathBar.vue';
import type { TopicBrowserItem } from '../../types/domain';

defineProps<{
  items: TopicBrowserItem[];
  breadcrumb: Array<{ label: string; path: string }>;
}>();

const emit = defineEmits<{
  (event: 'navigate', item: TopicBrowserItem): void;
  (event: 'select', item: TopicBrowserItem): void;
  (event: 'jump', path: string): void;
}>();

function handleClick(item: TopicBrowserItem) {
  if (item.kind === 'leaf') {
    emit('select', item);
    return;
  }
  emit('navigate', item);
}
</script>

<template>
  <section class="topic-browser-panel">
    <TopicPathBar :breadcrumb="breadcrumb" @jump="$emit('jump', $event)" />
    <div class="topic-list">
      <button
        v-for="item in items"
        :key="item.path"
        type="button"
        class="topic-item"
        @click="handleClick(item)"
      >
        <strong>{{ item.segment }}</strong>
        <span>{{ item.kind === 'leaf' ? 'Wert wählen' : 'Ebene öffnen' }}</span>
      </button>
    </div>
  </section>
</template>
