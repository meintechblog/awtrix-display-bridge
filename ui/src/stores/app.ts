import { defineStore } from 'pinia';

export const useAppStore = defineStore('app', {
  state: () => ({
    title: 'AWTRIX Dashboard',
    darkMode: true,
  }),
});
