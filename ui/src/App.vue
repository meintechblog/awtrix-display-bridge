<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router';
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div>
        <p class="eyebrow">AWTRIX Dashboard</p>
        <h1>Display Control Center</h1>
      </div>
      <nav class="primary-nav" aria-label="Primary">
        <RouterLink to="/">Dashboard</RouterLink>
        <RouterLink to="/displays">Displays</RouterLink>
        <RouterLink to="/inputs">Inputs</RouterLink>
        <RouterLink to="/settings">Settings</RouterLink>
      </nav>
    </header>

    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>
