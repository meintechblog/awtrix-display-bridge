import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import { fetchDiscoveredDisplays } from '../api/client';
import type { DiscoveryDisplay } from '../types/domain';

export function useDisplayDiscovery(existingIps: () => string[]) {
  const items = ref<DiscoveryDisplay[]>([]);
  const loading = ref(false);
  const error = ref('');
  const lastUpdatedAtMs = ref(0);
  const scanActive = ref(false);
  let pollTimer: ReturnType<typeof window.setInterval> | null = null;

  const filteredItems = computed(() => {
    const excluded = new Set(existingIps().map((ip) => String(ip || '').trim()).filter(Boolean));
    return items.value.filter((item) => !excluded.has(String(item.ip || '').trim()));
  });

  async function refresh(refresh = false) {
    loading.value = true;
    try {
      const snapshot = await fetchDiscoveredDisplays(refresh);
      items.value = snapshot.items || [];
      error.value = snapshot.error || '';
      lastUpdatedAtMs.value = Number(snapshot.updated_at_ms || 0);
      scanActive.value = Boolean(snapshot.scan_active);
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Discovery fehlgeschlagen.';
    } finally {
      loading.value = false;
    }
  }

  onMounted(() => {
    void refresh(false);
    pollTimer = window.setInterval(() => {
      void refresh(false);
    }, 10000);
  });

  onBeforeUnmount(() => {
    if (pollTimer) {
      window.clearInterval(pollTimer);
      pollTimer = null;
    }
  });

  return {
    items: filteredItems,
    loading,
    error,
    lastUpdatedAtMs,
    scanActive,
    refresh,
  };
}
