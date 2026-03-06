import { onBeforeUnmount, onMounted, watch } from 'vue';

import { useRuntimeStore } from '../stores/runtime';
import { useWorkspaceStore } from '../stores/workspace';

export function useRuntimeStream() {
  const runtime = useRuntimeStore();
  const workspace = useWorkspaceStore();

  let displayTimer: ReturnType<typeof window.setInterval> | null = null;
  let staleTimer: ReturnType<typeof window.setInterval> | null = null;

  const stopTimers = () => {
    if (displayTimer) window.clearInterval(displayTimer);
    if (staleTimer) window.clearInterval(staleTimer);
    displayTimer = null;
    staleTimer = null;
  };

  onMounted(() => {
    watch(
      () => workspace.displays.map((display) => `${display.id}:${display.ip}`).join('|'),
      async () => {
        await runtime.refreshDisplayStates(workspace.displays);
        if (displayTimer) window.clearInterval(displayTimer);
        displayTimer = window.setInterval(() => {
          void runtime.refreshDisplayStates(workspace.displays);
        }, 15000);
      },
      { immediate: true },
    );

    watch(
      () => workspace.mqttInputs.map((input) => `${input.id}:${input.brokerHost}:${input.brokerPort}:${input.topic}:${input.jsonKey}`).join('|'),
      () => {
        runtime.ensureBrokerStreams(workspace.mqttInputs);
      },
      { immediate: true },
    );

    staleTimer = window.setInterval(() => {
      runtime.markStaleAt(Date.now(), 20000);
    }, 5000);
  });

  onBeforeUnmount(() => {
    stopTimers();
    runtime.stopAllStreams();
  });
}
