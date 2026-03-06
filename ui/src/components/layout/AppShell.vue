<script setup lang="ts">
import AppHeader from './AppHeader.vue';
import AppSidebar from './AppSidebar.vue';
</script>

<template>
  <div class="shell">
    <AppHeader
      eyebrow="AWTRIX Dashboard"
      title="Display Control Center"
      subtitle="Dashboard-first orchestration for displays, inputs, and runtime state."
    />

    <div class="shell-grid">
      <AppSidebar />

      <main class="shell-main">
        <section class="shell-summary">
          <slot name="summary" />
        </section>
        <section class="shell-content">
          <slot />
        </section>
      </main>
    </div>
  </div>
</template>
