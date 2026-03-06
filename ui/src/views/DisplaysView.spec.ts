import { fireEvent, render, screen, waitFor } from '@testing-library/vue';
import { createPinia, setActivePinia } from 'pinia';
import { nextTick } from 'vue';
import { vi } from 'vitest';

import DisplaysView from './DisplaysView.vue';
import { useWorkspaceStore } from '../stores/workspace';

const fetchDiscoveredDisplays = vi.fn();
const fetchDisplayUpdateStatus = vi.fn();
const startDisplayUpdateJob = vi.fn();
const fetchDisplayUpdateJob = vi.fn();

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return {
    ...actual,
    fetchDiscoveredDisplays: (...args: unknown[]) => fetchDiscoveredDisplays(...args),
    fetchDisplayUpdateStatus: (...args: unknown[]) => fetchDisplayUpdateStatus(...args),
    startDisplayUpdateJob: (...args: unknown[]) => startDisplayUpdateJob(...args),
    fetchDisplayUpdateJob: (...args: unknown[]) => fetchDisplayUpdateJob(...args),
  };
});

beforeEach(() => {
  vi.useFakeTimers();
  fetchDiscoveredDisplays.mockReset();
  fetchDisplayUpdateStatus.mockReset();
  startDisplayUpdateJob.mockReset();
  fetchDisplayUpdateJob.mockReset();
});

afterEach(() => {
  vi.clearAllTimers();
  vi.useRealTimers();
});

test('adopts a discovered display into the unsaved display list', async () => {
  const pinia = createPinia();
  setActivePinia(pinia);
  const workspace = useWorkspaceStore();
  workspace.$patch({
    displays: [{ id: 'display-main', name: 'Display 1', ip: '192.168.3.126' }],
    inputs: [],
    bindings: [],
    persistedConfig: {
      version: 1,
      displays: [{ id: 'display-main', name: 'Display 1', ip: '192.168.3.126' }],
      inputs: [],
      bindings: [],
    },
    saveState: 'saved',
    loaded: true,
  });

  fetchDiscoveredDisplays.mockResolvedValue({
    items: [
      {
        ip: '192.168.3.140',
        name: 'Desk Matrix',
        version: '0.97',
        app: 'Clock',
        wifiSignal: -61,
        matrix: true,
        updatedAtMs: 1772870400000,
      },
    ],
    count: 1,
    error: '',
    updated_at_ms: 1772870400000,
    scan_active: false,
  });
  fetchDisplayUpdateStatus
    .mockImplementationOnce(async (ip: string) => ({
      ip,
      currentVersion: '0.96',
      latestVersion: '0.98',
      updateAvailable: true,
      app: 'Clock',
      checkedAtMs: 1772870400000,
      error: '',
    }))
    .mockImplementationOnce(async (ip: string) => ({
      ip,
      currentVersion: '0.98',
      latestVersion: '0.98',
      updateAvailable: false,
      app: 'Notification',
      checkedAtMs: 1772870500000,
      error: '',
    }));
  startDisplayUpdateJob.mockResolvedValue({
    jobId: 'job-123',
    ip: '192.168.3.126',
    phase: 'checking',
    message: 'Pruefe Firmware...',
    done: false,
    ok: false,
    result: {},
  });
  fetchDisplayUpdateJob
    .mockResolvedValueOnce({
      jobId: 'job-123',
      ip: '192.168.3.126',
      phase: 'uploading',
      message: 'Uebertrage Firmware...',
      done: false,
      ok: false,
      result: {},
    })
    .mockResolvedValueOnce({
      jobId: 'job-123',
      ip: '192.168.3.126',
      phase: 'completed',
      message: 'Update erfolgreich auf 0.98.',
      done: true,
      ok: true,
      result: { finalVersion: '0.98' },
    });

  render(DisplaysView, {
    global: {
      plugins: [pinia],
    },
  });

  expect(await screen.findByText('Version 0.96')).toBeInTheDocument();
  expect(fetchDisplayUpdateStatus).toHaveBeenCalledWith('192.168.3.126', false);
  expect(screen.getByRole('button', { name: 'Update auf 0.98' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Webinterface' })).toBeInTheDocument();

  await fireEvent.click(screen.getByRole('button', { name: 'Update auf 0.98' }));

  await waitFor(() => {
    expect(startDisplayUpdateJob).toHaveBeenCalledWith('192.168.3.126');
  });
  await vi.advanceTimersByTimeAsync(1000);
  await nextTick();
  expect(await screen.findByRole('button', { name: 'Übertrage...' })).toBeInTheDocument();
  await vi.advanceTimersByTimeAsync(1000);
  await nextTick();
  expect(await screen.findByRole('button', { name: 'Aktuell · 0.98' })).toBeInTheDocument();
  expect(screen.queryByText('Fetch is aborted')).not.toBeInTheDocument();
  expect(await screen.findByText('Desk Matrix')).toBeInTheDocument();

  await fireEvent.click(screen.getByRole('button', { name: 'Adoptieren' }));

  await waitFor(() => {
    expect(screen.queryByRole('button', { name: 'Adoptieren' })).not.toBeInTheDocument();
  });
  expect(screen.getByDisplayValue('192.168.3.140')).toBeInTheDocument();
  expect(workspace.saveState).toBe('dirty');
});

test('renders a passive current-state update pill when no update is available', async () => {
  const pinia = createPinia();
  setActivePinia(pinia);
  const workspace = useWorkspaceStore();
  workspace.$patch({
    displays: [{ id: 'display-main', name: 'Display 1', ip: '192.168.3.126' }],
    inputs: [],
    bindings: [],
    persistedConfig: {
      version: 1,
      displays: [{ id: 'display-main', name: 'Display 1', ip: '192.168.3.126' }],
      inputs: [],
      bindings: [],
    },
    saveState: 'saved',
    loaded: true,
  });

  fetchDiscoveredDisplays.mockResolvedValue({
    items: [],
    count: 0,
    error: '',
    updated_at_ms: 1772870400000,
    scan_active: false,
  });
  fetchDisplayUpdateStatus.mockResolvedValue({
    ip: '192.168.3.126',
    currentVersion: '0.98',
    latestVersion: '0.98',
    updateAvailable: false,
    app: 'Notification',
    checkedAtMs: 1772870400000,
    error: '',
  });

  render(DisplaysView, {
    global: {
      plugins: [pinia],
    },
  });

  expect(await screen.findByText('Version 0.98')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Aktuell · 0.98' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Update auf 0.98' })).not.toBeInTheDocument();
});

test('clicking the current-state update element triggers a manual re-check', async () => {
  const pinia = createPinia();
  setActivePinia(pinia);
  const workspace = useWorkspaceStore();
  workspace.$patch({
    displays: [{ id: 'display-main', name: 'Display 1', ip: '192.168.3.126' }],
    inputs: [],
    bindings: [],
    persistedConfig: {
      version: 1,
      displays: [{ id: 'display-main', name: 'Display 1', ip: '192.168.3.126' }],
      inputs: [],
      bindings: [],
    },
    saveState: 'saved',
    loaded: true,
  });

  fetchDiscoveredDisplays.mockResolvedValue({
    items: [],
    count: 0,
    error: '',
    updated_at_ms: 1772870400000,
    scan_active: false,
  });
  fetchDisplayUpdateStatus
    .mockResolvedValueOnce({
      ip: '192.168.3.126',
      currentVersion: '0.98',
      latestVersion: '0.98',
      updateAvailable: false,
      app: 'Clock',
      checkedAtMs: 1772870400000,
      error: '',
    })
    .mockResolvedValueOnce({
      ip: '192.168.3.126',
      currentVersion: '0.98',
      latestVersion: '0.99',
      updateAvailable: true,
      app: 'Clock',
      checkedAtMs: 1772870500000,
      error: '',
    });

  render(DisplaysView, {
    global: {
      plugins: [pinia],
    },
  });

  const currentButton = await screen.findByRole('button', { name: 'Aktuell · 0.98' });
  await fireEvent.click(currentButton);

  await waitFor(() => {
    expect(fetchDisplayUpdateStatus).toHaveBeenNthCalledWith(2, '192.168.3.126', true);
  });
  expect(await screen.findByRole('button', { name: 'Update auf 0.99' })).toBeInTheDocument();
});
