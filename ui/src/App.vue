<script setup lang="ts">
import { RouterView } from 'vue-router';

import AppShell from './components/layout/AppShell.vue';
</script>

<template>
  <AppShell>
    <template #summary>
      <div class="summary-strip">
        <div class="summary-card">
          <p class="eyebrow">Runtime</p>
          <strong>Bridge Online</strong>
          <span>API, MQTT and Display runtime move into live widgets in the next tasks.</span>
        </div>
        <div class="summary-card">
          <p class="eyebrow">Scope</p>
          <strong>Multi-Display Ready</strong>
          <span>The shell is now prepared for EVCC-style summary cards and display grids.</span>
        </div>
      </div>
    </template>

    <main class="app-main">
      <RouterView />
    </main>
  </AppShell>
</template>
