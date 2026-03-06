import { render, screen } from '@testing-library/vue';
import { createPinia } from 'pinia';
import { createMemoryHistory, createRouter } from 'vue-router';

import App from './App.vue';

test('renders the primary navigation entries', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div>Overview</div>' } },
      { path: '/displays', component: { template: '<div>Displays page</div>' } },
      { path: '/skills', component: { template: '<div>Skills page</div>' } },
      { path: '/settings', component: { template: '<div>Settings page</div>' } },
    ],
  });

  render(App, {
    global: {
      plugins: [createPinia(), router],
    },
  });

  expect(await screen.findByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Displays' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Skills' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Settings' })).toBeInTheDocument();
});
