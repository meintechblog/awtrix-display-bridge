<script setup lang="ts">
defineProps<{
  eyebrow: string;
  title: string;
  subtitle: string;
}>();
</script>

<template>
  <header class="shell-header">
    <div>
      <p class="eyebrow">{{ eyebrow }}</p>
      <h1>{{ title }}</h1>
    </div>
    <p class="shell-subtitle">{{ subtitle }}</p>
  </header>
</template>
