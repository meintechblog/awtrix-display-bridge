import { beforeEach, expect, test, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

import type { AppConfigPayload } from '../types/domain';
import { useWorkspaceStore } from './workspace';

const fetchConfig = vi.fn<() => Promise<AppConfigPayload>>();
const saveConfig = vi.fn<(payload: AppConfigPayload) => Promise<AppConfigPayload>>();
const replaceAutoRoutes = vi.fn<() => Promise<{ count: number }>>();

vi.mock('../api/client', () => ({
  fetchConfig: () => fetchConfig(),
  saveConfig: (payload: AppConfigPayload) => saveConfig(payload),
  replaceAutoRoutes: () => replaceAutoRoutes(),
}));

const basePayload: AppConfigPayload = {
  version: 1,
  updated_at: 1772870400000,
  displays: [{ id: 'display-main', name: 'Display 1', ip: '192.168.3.126' }],
  inputs: [
    {
      id: 'mqtt-1',
      kind: 'mqtt',
      name: 'MQTT Balance',
      brokerHost: '192.168.3.8',
      brokerPort: 1883,
      topic: 'trading-deluxxe/webapp/status/balance',
      jsonKey: '',
      template: 'Balance: {value}',
      displayMode: '8',
      autoMode: 'off',
      timeout: 4,
      topicSearch: '',
    },
  ],
  bindings: [{ id: 'binding-1', inputId: 'mqtt-1', displayIds: ['display-main'], enabled: true }],
};

beforeEach(() => {
  setActivePinia(createPinia());
  fetchConfig.mockReset();
  saveConfig.mockReset();
  replaceAutoRoutes.mockReset();
  fetchConfig.mockResolvedValue(structuredClone(basePayload));
  saveConfig.mockImplementation(async (payload) => structuredClone(payload));
  replaceAutoRoutes.mockResolvedValue({ count: 0 });
});

test('marks mqtt edits as dirty without persisting immediately', async () => {
  const store = useWorkspaceStore();

  await store.load();
  saveConfig.mockClear();

  store.updateInput('mqtt-1', { topic: 'trading-deluxxe/webapp/status/equity' });

  expect(store.saveState).toBe('dirty');
  expect(store.hasUnsavedChanges).toBe(true);
  expect(store.inputSaveState('mqtt-1')).toBe('dirty');
  expect(saveConfig).not.toHaveBeenCalled();
});

test('discardChanges restores the last saved mqtt input state', async () => {
  const store = useWorkspaceStore();

  await store.load();
  store.updateInput('mqtt-1', { topic: 'trading-deluxxe/webapp/status/equity' });

  store.discardChanges();

  expect(store.inputById('mqtt-1')?.kind).toBe('mqtt');
  expect((store.inputById('mqtt-1') as { topic?: string } | undefined)?.topic).toBe('trading-deluxxe/webapp/status/balance');
  expect(store.hasUnsavedChanges).toBe(false);
  expect(store.saveState).toBe('saved');
});

test('saveNow persists dirty config explicitly', async () => {
  const store = useWorkspaceStore();

  await store.load();
  store.updateInput('mqtt-1', { topic: 'trading-deluxxe/webapp/status/equity' });

  await store.saveNow();

  expect(saveConfig).toHaveBeenCalledTimes(1);
  expect(store.hasUnsavedChanges).toBe(false);
  expect(store.saveState).toBe('saved');
  expect(store.inputSaveState('mqtt-1')).toBe('saved');
});
