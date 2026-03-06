<script setup lang="ts">
defineProps<{
  item: {
    ip: string;
    name: string;
    version?: string;
    app?: string;
    wifiSignal?: number | null;
    matrix?: boolean | null;
  };
}>();

defineEmits<{
  (event: 'adopt'): void;
}>();
</script>

<template>
  <article class="discovery-card">
    <div class="discovery-card-head">
      <div>
        <p class="eyebrow">Im Netzwerk</p>
        <h3>{{ item.name }}</h3>
        <span class="meta-copy">{{ item.ip }}</span>
      </div>
      <button type="button" class="primary-btn" @click="$emit('adopt')">Adoptieren</button>
    </div>

    <div class="tag-row">
      <span v-if="item.version" class="tag-pill">Version {{ item.version }}</span>
      <span v-if="item.app" class="tag-pill">App {{ item.app }}</span>
      <span v-if="typeof item.wifiSignal === 'number'" class="tag-pill">Signal {{ item.wifiSignal }}</span>
      <span v-if="typeof item.matrix === 'boolean'" class="tag-pill">Matrix {{ item.matrix ? 'an' : 'aus' }}</span>
    </div>
  </article>
</template>
