<script setup lang="ts">
import type { DashboardSummary } from '../../types/domain';

defineProps<{
  summary: DashboardSummary;
}>();
</script>

<template>
  <section class="summary-grid">
    <article class="summary-tile">
      <p class="eyebrow">Displays</p>
      <strong>{{ summary.displays }}</strong>
      <span>{{ summary.online }} online · {{ summary.offline }} offline · {{ summary.stale }} stale</span>
    </article>
    <article class="summary-tile">
      <p class="eyebrow">Inputs</p>
      <strong>{{ summary.inputs }}</strong>
      <span>{{ summary.bindings }} aktive Zuordnungen</span>
    </article>
    <article class="summary-tile">
      <p class="eyebrow">Broker</p>
      <strong>{{ summary.liveBrokers }}</strong>
      <span>Live-Streams für konfigurierte MQTT-Topics</span>
    </article>
  </section>
</template>
