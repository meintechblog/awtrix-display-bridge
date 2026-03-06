import { onBeforeUnmount, onMounted, ref } from 'vue';

import { fetchDisplayUpdateJob, fetchDisplayUpdateStatus, startDisplayUpdateJob } from '../api/client';
import type { DisplayConfig, DisplayUpdateJob, DisplayUpdateStatus } from '../types/domain';

type DisplayUpdateState = Record<string, DisplayUpdateStatus>;
type DisplayJobState = Record<string, DisplayUpdateJob>;

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

function phaseLabel(job: DisplayUpdateJob): string {
  switch (job.phase) {
    case 'checking':
      return 'Prüfe...';
    case 'downloading':
      return 'Lade Firmware...';
    case 'uploading':
      return 'Übertrage...';
    case 'rebooting':
      return 'Rebootet...';
    case 'verifying':
      return 'Prüfe Version...';
    case 'failed':
      return 'Update fehlgeschlagen';
    case 'completed':
      return '';
    default:
      return 'Update läuft...';
  }
}

export function useDisplayUpdates(displays: () => DisplayConfig[]) {
  const statuses = ref<DisplayUpdateState>({});
  const jobs = ref<DisplayJobState>({});
  const checking = ref<Record<string, boolean>>({});
  const actionMessages = ref<Record<string, string>>({});
  const pollTimers = new Map<string, ReturnType<typeof window.setTimeout>>();

  function clearPollTimer(displayId: string) {
    const timer = pollTimers.get(displayId);
    if (timer) {
      window.clearTimeout(timer);
      pollTimers.delete(displayId);
    }
  }

  function schedulePoll(displayId: string, jobId: string, ip: string) {
    clearPollTimer(displayId);
    pollTimers.set(displayId, window.setTimeout(() => {
      void pollJob(displayId, jobId, ip);
    }, 1000));
  }

  async function refreshOne(displayId: string, ip: string, refresh = false) {
    if (!ip) {
      statuses.value[displayId] = emptyStatus('', 'IP fehlt.');
      return;
    }
    checking.value[displayId] = true;
    actionMessages.value[displayId] = '';
    try {
      statuses.value[displayId] = await fetchDisplayUpdateStatus(ip, refresh);
    } catch (error) {
      statuses.value[displayId] = emptyStatus(ip, error instanceof Error ? error.message : 'Firmware-Status fehlgeschlagen.');
    } finally {
      checking.value[displayId] = false;
    }
  }

  async function refreshAll(refresh = false) {
    const currentIds = new Set(displays().map((display) => display.id));
    await Promise.all(displays().map((display) => refreshOne(display.id, display.ip, refresh)));
    Object.keys(statuses.value).forEach((displayId) => {
      if (!currentIds.has(displayId)) {
        delete statuses.value[displayId];
        delete jobs.value[displayId];
        delete checking.value[displayId];
        delete actionMessages.value[displayId];
        clearPollTimer(displayId);
      }
    });
  }

  async function pollJob(displayId: string, jobId: string, ip: string) {
    try {
      const job = await fetchDisplayUpdateJob(jobId);
      jobs.value[displayId] = job;
      actionMessages.value[displayId] = job.done && !job.ok ? (job.message || 'Update fehlgeschlagen.') : '';
      if (job.done) {
        clearPollTimer(displayId);
        await refreshOne(displayId, ip, true);
        return;
      }
      schedulePoll(displayId, jobId, ip);
    } catch (error) {
      clearPollTimer(displayId);
      actionMessages.value[displayId] = error instanceof Error ? error.message : 'Update-Status fehlgeschlagen.';
    }
  }

  async function handleUpdateAction(displayId: string, ip: string) {
    if (!ip) {
      actionMessages.value[displayId] = 'IP fehlt.';
      return;
    }
    const activeJob = jobs.value[displayId];
    if (checking.value[displayId] || (activeJob && !activeJob.done)) {
      return;
    }

    const status = statuses.value[displayId];
    actionMessages.value[displayId] = '';
    if (status?.updateAvailable) {
      try {
        const job = await startDisplayUpdateJob(ip);
        jobs.value[displayId] = job;
        if (job.done) {
          actionMessages.value[displayId] = job.ok ? '' : (job.message || 'Update fehlgeschlagen.');
          await refreshOne(displayId, ip, true);
          return;
        }
        schedulePoll(displayId, job.jobId, ip);
      } catch {
        actionMessages.value[displayId] = 'Update konnte nicht gestartet werden.';
      }
      return;
    }

    await refreshOne(displayId, ip, true);
  }

  function ctaLabel(displayId: string): string {
    if (checking.value[displayId]) {
      return 'Prüfe...';
    }
    const job = jobs.value[displayId];
    if (job && !job.done) {
      return phaseLabel(job);
    }
    if (job?.phase === 'failed') {
      return 'Update fehlgeschlagen';
    }
    const status = statuses.value[displayId];
    const latestVersion = String(status?.latestVersion || '').trim();
    if (status?.updateAvailable && latestVersion) {
      return `Update auf ${latestVersion}`;
    }
    if (latestVersion) {
      return `Aktuell · ${latestVersion}`;
    }
    return 'Update prüfen';
  }

  function ctaClass(displayId: string): string {
    if (checking.value[displayId]) {
      return 'ghost-btn';
    }
    const job = jobs.value[displayId];
    if (job && !job.done) {
      return 'ghost-btn';
    }
    if (job?.phase === 'failed') {
      return 'danger-btn';
    }
    if (statuses.value[displayId]?.updateAvailable) {
      return 'primary-btn';
    }
    return 'tag-pill action-pill';
  }

  function ctaDisabled(displayId: string): boolean {
    return Boolean(checking.value[displayId] || (jobs.value[displayId] && !jobs.value[displayId].done));
  }

  onMounted(() => {
    void refreshAll(false);
  });

  onBeforeUnmount(() => {
    Array.from(pollTimers.keys()).forEach(clearPollTimer);
  });

  return {
    statuses,
    jobs,
    checking,
    actionMessages,
    refreshAll,
    handleUpdateAction,
    ctaLabel,
    ctaClass,
    ctaDisabled,
  };
}
