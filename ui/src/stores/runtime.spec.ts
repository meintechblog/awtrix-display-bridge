import { createPinia, setActivePinia } from 'pinia';
import { vi } from 'vitest';

import { useRuntimeStore } from './runtime';

const fetchDisplayStats = vi.fn();

vi.mock('../api/client', () => ({
  fetchDisplayStats: (ip: string) => fetchDisplayStats(ip),
}));

test('marks a display as stale when no runtime event arrives within threshold', () => {
  setActivePinia(createPinia());
  const store = useRuntimeStore();

  store.upsertDisplayState({
    displayId: 'd-1',
    state: 'online',
    updatedAtMs: 1000,
  });

  store.markStaleAt(9000, 5000);

  expect(store.displayStates['d-1'].state).toBe('stale');
});

test('extracts battery state from display stats', async () => {
  setActivePinia(createPinia());
  const store = useRuntimeStore();
  fetchDisplayStats.mockResolvedValueOnce({
    version: '0.98',
    app: 'Notification',
    bat: 47,
    bat_raw: 565,
    wifi_signal: -61,
    matrix: true,
  });

  await store.refreshDisplayStates([{ id: 'd-1', name: 'Main', ip: '192.168.3.126' }]);

  expect(store.displayStates['d-1'].batteryLevel).toBe(47);
  expect(store.displayStates['d-1'].batteryRaw).toBe(565);
  expect(store.displayStates['d-1'].externalPowerHint).toBe(false);
});
