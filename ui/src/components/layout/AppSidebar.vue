<script setup lang="ts">
import { RouterLink } from 'vue-router';

const items = [
  { to: '/', label: 'Dashboard' },
  { to: '/displays', label: 'Displays' },
  { to: '/inputs', label: 'Inputs' },
  { to: '/settings', label: 'Settings' },
];
</script>

<template>
  <aside class="shell-sidebar">
    <RouterLink
      v-for="item in items"
      :key="item.to"
      :to="item.to"
      class="shell-nav-link"
    >
      {{ item.label }}
    </RouterLink>
  </aside>
</template>
