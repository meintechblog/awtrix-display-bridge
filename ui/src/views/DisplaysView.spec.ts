import { fireEvent, render, screen, waitFor } from '@testing-library/vue';
import { createPinia, setActivePinia } from 'pinia';
import { vi } from 'vitest';

import DisplaysView from './DisplaysView.vue';
import { useWorkspaceStore } from '../stores/workspace';

const fetchDiscoveredDisplays = vi.fn();
const fetchDisplayUpdateStatus = vi.fn();
const triggerDisplayUpdate = vi.fn();

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return {
    ...actual,
    fetchDiscoveredDisplays: (...args: unknown[]) => fetchDiscoveredDisplays(...args),
    fetchDisplayUpdateStatus: (...args: unknown[]) => fetchDisplayUpdateStatus(...args),
    triggerDisplayUpdate: (...args: unknown[]) => triggerDisplayUpdate(...args),
  };
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
  fetchDisplayUpdateStatus.mockImplementation(async (ip: string) => ({
    ip,
    currentVersion: '0.96',
    latestVersion: '0.98',
    updateAvailable: true,
    app: 'Clock',
    checkedAtMs: 1772870400000,
    error: '',
  }));
  triggerDisplayUpdate.mockResolvedValue({
    ip: '192.168.3.126',
    statusCode: 404,
    body: 'NoUpdateFound',
    ok: false,
  });

  render(DisplaysView, {
    global: {
      plugins: [pinia],
    },
  });

  expect(await screen.findByText('Version 0.96')).toBeInTheDocument();
  expect(screen.getByText('Neueste 0.98')).toBeInTheDocument();
  expect(screen.getByText('Update verfügbar')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Update versuchen' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Webinterface' })).toBeInTheDocument();

  await fireEvent.click(screen.getByRole('button', { name: 'Update versuchen' }));

  await waitFor(() => {
    expect(triggerDisplayUpdate).toHaveBeenCalledWith('192.168.3.126');
  });
  expect(await screen.findByText('NoUpdateFound')).toBeInTheDocument();
  expect(await screen.findByText('Desk Matrix')).toBeInTheDocument();

  await fireEvent.click(screen.getByRole('button', { name: 'Adoptieren' }));

  await waitFor(() => {
    expect(screen.queryByRole('button', { name: 'Adoptieren' })).not.toBeInTheDocument();
  });
  expect(screen.getByDisplayValue('192.168.3.140')).toBeInTheDocument();
  expect(workspace.saveState).toBe('dirty');
});
