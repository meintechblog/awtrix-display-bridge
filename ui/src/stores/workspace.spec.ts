import { beforeEach, expect, test, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

import type { AppConfigPayload, DiscoveryDisplay } from '../types/domain';
import { useWorkspaceStore } from './workspace';

const fetchConfig = vi.fn<() => Promise<AppConfigPayload>>();
const saveConfig = vi.fn<(payload: AppConfigPayload) => Promise<AppConfigPayload>>();
const replaceAutoRoutes = vi.fn<(displayIp: string, routes: unknown[]) => Promise<{ count: number }>>();

vi.mock('../api/client', () => ({
  fetchConfig: () => fetchConfig(),
  saveConfig: (payload: AppConfigPayload) => saveConfig(payload),
  replaceAutoRoutes: (displayIp: string, routes: unknown[]) => replaceAutoRoutes(displayIp, routes),
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
      timeout: 4,
      topicSearch: '',
      delivery: {
        template: 'Balance: {value}',
        sendMode: 'off',
        displayDuration: '8',
      },
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

test('legacy flat mqtt fields load into the generic delivery model', async () => {
  fetchConfig.mockResolvedValueOnce({
    ...structuredClone(basePayload),
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
        autoMode: 'realtime',
        timeout: 4,
        topicSearch: '',
      },
    ],
  });

  const store = useWorkspaceStore();
  await store.load();
  const skill = store.inputById('mqtt-1');

  expect(skill?.kind).toBe('mqtt');
  expect(skill && 'delivery' in skill ? skill.delivery.sendMode : '').toBe('realtime');
  expect(skill && 'delivery' in skill ? skill.delivery.displayDuration : '').toBe('8');
  expect(skill && 'delivery' in skill ? skill.delivery.template : '').toBe('Balance: {value}');
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

test('syncAutoRoutes builds routes from generic delivery config', async () => {
  const store = useWorkspaceStore();
  await store.load();

  await store.syncAutoRoutes();

  expect(replaceAutoRoutes).toHaveBeenCalledTimes(1);
  const [, routes] = replaceAutoRoutes.mock.calls[0] ?? [];
  expect(routes).toEqual([]);

  store.updateInput('mqtt-1', {
    delivery: {
      template: 'Balance: {value}',
      sendMode: '2',
      displayDuration: '6',
    },
  });
  await store.syncAutoRoutes();

  const secondCall = replaceAutoRoutes.mock.calls[1];
  expect(secondCall[1]).toEqual([
    expect.objectContaining({
      topic: 'trading-deluxxe/webapp/status/balance',
      template: 'Balance: {value}',
      send_mode: '2',
      display_duration: '6',
    }),
  ]);
});

test('adoptDiscoveredDisplay adds a draft display without persisting immediately', async () => {
  const store = useWorkspaceStore();

  await store.load();
  saveConfig.mockClear();

  store.adoptDiscoveredDisplay({
    ip: '192.168.3.140',
    name: 'Desk Matrix',
    version: '0.97',
    app: 'Clock',
    wifiSignal: -61,
    matrix: true,
    updatedAtMs: 1772870400000,
  } satisfies DiscoveryDisplay);

  expect(store.displays.some((display) => display.ip === '192.168.3.140')).toBe(true);
  expect(store.hasUnsavedChanges).toBe(true);
  expect(store.saveState).toBe('dirty');
  expect(saveConfig).not.toHaveBeenCalled();
});
