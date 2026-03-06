import { onBeforeUnmount, onMounted, ref } from 'vue';

import { fetchDisplayUpdateStatus, triggerDisplayUpdate } from '../api/client';
import type { DisplayConfig, DisplayUpdateStatus } from '../types/domain';

type DisplayUpdateState = Record<string, DisplayUpdateStatus>;

function emptyStatus(ip: string, error = ''): DisplayUpdateStatus {
  return {
    ip,
    currentVersion: '',
    latestVersion: '',
    updateAvailable: false,
    app: '',
    checkedAtMs: Date.now(),
    error,
  };
}

export function useDisplayUpdates(displays: () => DisplayConfig[]) {
  const statuses = ref<DisplayUpdateState>({});
  const updating = ref<Record<string, boolean>>({});
  const actionMessages = ref<Record<string, string>>({});
  let pollTimer: ReturnType<typeof window.setInterval> | null = null;

  async function refreshOne(displayId: string, ip: string, refresh = false) {
    if (!ip) {
      statuses.value[displayId] = emptyStatus('', 'IP fehlt.');
      return;
    }
    try {
      statuses.value[displayId] = await fetchDisplayUpdateStatus(ip, refresh);
    } catch (error) {
      statuses.value[displayId] = emptyStatus(ip, error instanceof Error ? error.message : 'Firmware-Status fehlgeschlagen.');
    }
  }

  async function refreshAll(refresh = false) {
    const currentIds = new Set(displays().map((display) => display.id));
    await Promise.all(displays().map((display) => refreshOne(display.id, display.ip, refresh)));
    Object.keys(statuses.value).forEach((displayId) => {
      if (!currentIds.has(displayId)) {
        delete statuses.value[displayId];
      }
    });
  }

  async function tryUpdate(displayId: string, ip: string) {
    if (!ip) {
      actionMessages.value[displayId] = 'IP fehlt.';
      return;
    }
    updating.value[displayId] = true;
    try {
      const result = await triggerDisplayUpdate(ip);
      actionMessages.value[displayId] = result.body || (result.ok ? 'Update angestoßen.' : `HTTP ${result.statusCode}`);
      await refreshOne(displayId, ip, true);
    } catch (error) {
      actionMessages.value[displayId] = error instanceof Error ? error.message : 'Update fehlgeschlagen.';
    } finally {
      updating.value[displayId] = false;
    }
  }

  onMounted(() => {
    void refreshAll(false);
    pollTimer = window.setInterval(() => {
      void refreshAll(false);
    }, 60000);
  });

  onBeforeUnmount(() => {
    if (pollTimer) {
      window.clearInterval(pollTimer);
      pollTimer = null;
    }
  });

  return {
    statuses,
    updating,
    actionMessages,
    refreshAll,
    tryUpdate,
  };
}
