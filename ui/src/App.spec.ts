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
      { path: '/inputs', component: { template: '<div>Inputs page</div>' } },
      { path: '/settings', component: { template: '<div>Settings page</div>' } },
    ],
  });

  render(App, {
    global: {
      plugins: [createPinia(), router],
    },
  });

  expect(await screen.findByText('Dashboard')).toBeInTheDocument();
  expect(screen.getByText('Displays')).toBeInTheDocument();
  expect(screen.getByText('Inputs')).toBeInTheDocument();
  expect(screen.getByText('Settings')).toBeInTheDocument();
});
