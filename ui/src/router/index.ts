import { createRouter, createWebHistory } from 'vue-router';

import DashboardView from '../views/DashboardView.vue';
import DisplaysView from '../views/DisplaysView.vue';
import InputsView from '../views/InputsView.vue';
import SettingsView from '../views/SettingsView.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: DashboardView },
    { path: '/displays', name: 'displays', component: DisplaysView },
    { path: '/inputs', name: 'inputs', component: InputsView },
    { path: '/settings', name: 'settings', component: SettingsView },
  ],
});

export default router;
