import { render, screen } from '@testing-library/vue';
import { createPinia } from 'pinia';
import { createMemoryHistory, createRouter } from 'vue-router';

import AppShell from './AppShell.vue';

test('renders summary slot, navigation, and content shell', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div>Dashboard content</div>' } },
      { path: '/displays', component: { template: '<div>Displays page</div>' } },
      { path: '/skills', component: { template: '<div>Skills page</div>' } },
      { path: '/settings', component: { template: '<div>Settings page</div>' } },
    ],
  });

  render(AppShell, {
    global: {
      plugins: [createPinia(), router],
    },
    slots: {
      summary: '<div>Runtime Summary</div>',
      default: '<div>Dashboard content</div>',
    },
  });

  expect(await screen.findByText('Runtime Summary')).toBeInTheDocument();
  expect(screen.getByText('Dashboard')).toBeInTheDocument();
  expect(screen.getByText('Dashboard content')).toBeInTheDocument();
});
