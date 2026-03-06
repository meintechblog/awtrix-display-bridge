import { createPinia, setActivePinia } from 'pinia';

import { useRuntimeStore } from './runtime';

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
