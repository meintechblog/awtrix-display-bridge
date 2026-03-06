import { defineStore } from 'pinia';

import { fetchDisplayStats } from '../api/client';
import type { DisplayConfig, DisplayRuntimeState, InputRuntimeValue, MqttInputConfig } from '../types/domain';
import { extractValueFromPayload } from '../utils/mqtt';

type StreamState = {
  state: 'idle' | 'connecting' | 'open' | 'error';
  topics: string[];
  lastEventAtMs: number;
  error: string;
};

const brokerStreams = new Map<string, { signature: string; source: EventSource }>();

function brokerKey(input: Pick<MqttInputConfig, 'brokerHost' | 'brokerPort'>): string {
  return `${input.brokerHost}:${input.brokerPort}`;
}

export const useRuntimeStore = defineStore('runtime', {
  state: () => ({
    displayStates: {} as Record<string, DisplayRuntimeState>,
    inputValues: {} as Record<string, InputRuntimeValue>,
    streamStates: {} as Record<string, StreamState>,
  }),
  getters: {
    connectedBrokerCount: (state) => Object.values(state.streamStates).filter((item) => item.state === 'open').length,
  },
  actions: {
    upsertDisplayState(payload: { displayId: string; state: DisplayRuntimeState['state']; updatedAtMs: number; version?: string; app?: string; wifiSignal?: number | null; matrix?: boolean | null; batteryLevel?: number | null; batteryRaw?: number | null; externalPowerHint?: boolean; error?: string }) {
      this.displayStates[payload.displayId] = {
        ...(this.displayStates[payload.displayId] || {}),
        state: payload.state,
        updatedAtMs: payload.updatedAtMs,
        version: payload.version,
        app: payload.app,
        wifiSignal: payload.wifiSignal ?? null,
        matrix: payload.matrix ?? null,
        batteryLevel: payload.batteryLevel ?? null,
        batteryRaw: payload.batteryRaw ?? null,
        externalPowerHint: payload.externalPowerHint ?? false,
        error: payload.error || '',
      };
    },
    setInputValue(inputId: string, payload: InputRuntimeValue) {
      this.inputValues[inputId] = payload;
    },
    markStaleAt(nowMs: number, staleThresholdMs: number) {
      Object.entries(this.displayStates).forEach(([displayId, state]) => {
        if (state.state === 'offline') {
          return;
        }
        if ((nowMs - state.updatedAtMs) > staleThresholdMs) {
          this.displayStates[displayId] = { ...state, state: 'stale' };
        }
      });
    },
    async refreshDisplayStates(displays: DisplayConfig[]) {
      await Promise.all(displays.map(async (display) => {
        try {
          const stats = await fetchDisplayStats(display.ip);
          this.upsertDisplayState({
            displayId: display.id,
            state: 'online',
            updatedAtMs: Date.now(),
            version: typeof stats.version === 'string' ? stats.version : undefined,
            app: typeof stats.app === 'string' ? stats.app : undefined,
            wifiSignal: typeof stats.wifi_signal === 'number' ? stats.wifi_signal : null,
            matrix: typeof stats.matrix === 'boolean' ? stats.matrix : null,
            batteryLevel: typeof stats.bat === 'number' ? stats.bat : null,
            batteryRaw: typeof stats.bat_raw === 'number' ? stats.bat_raw : null,
            externalPowerHint: typeof stats.bat === 'number' ? stats.bat >= 100 : false,
          });
        } catch (error) {
          this.upsertDisplayState({
            displayId: display.id,
            state: 'offline',
            updatedAtMs: Date.now(),
            error: error instanceof Error ? error.message : 'Display nicht erreichbar.',
          });
        }
      }));
    },
    ensureBrokerStreams(inputs: MqttInputConfig[]) {
      const grouped = new Map<string, { brokerHost: string; brokerPort: number; topics: string[] }>();
      inputs
        .filter((input) => input.brokerHost && input.topic)
        .forEach((input) => {
          const key = brokerKey(input);
          const entry = grouped.get(key) || {
            brokerHost: input.brokerHost,
            brokerPort: input.brokerPort,
            topics: [],
          };
          if (!entry.topics.includes(input.topic)) {
            entry.topics.push(input.topic);
          }
          grouped.set(key, entry);
        });

      Array.from(brokerStreams.keys()).forEach((key) => {
        if (!grouped.has(key)) {
          brokerStreams.get(key)?.source.close();
          brokerStreams.delete(key);
          this.streamStates[key] = { state: 'idle', topics: [], lastEventAtMs: 0, error: '' };
        }
      });

      grouped.forEach((entry, key) => {
        const signature = entry.topics.slice().sort().join('|');
        if (brokerStreams.get(key)?.signature === signature) {
          return;
        }

        brokerStreams.get(key)?.source.close();

        const url = new URL('/api/runtime/events', `${window.location.protocol}//${window.location.hostname}:8090`);
        url.searchParams.set('broker_host', entry.brokerHost);
        url.searchParams.set('broker_port', String(entry.brokerPort));
        entry.topics.forEach((topic) => url.searchParams.append('topic', topic));

        const source = new EventSource(url.toString());
        this.streamStates[key] = { state: 'connecting', topics: entry.topics, lastEventAtMs: 0, error: '' };

        source.onopen = () => {
          this.streamStates[key] = { state: 'open', topics: entry.topics, lastEventAtMs: Date.now(), error: '' };
        };

        source.onerror = () => {
          this.streamStates[key] = { ...this.streamStates[key], state: 'error', error: 'Live-Stream unterbrochen.' };
        };

        source.addEventListener('runtime', (rawEvent) => {
          try {
            const parsed = JSON.parse((rawEvent as MessageEvent).data) as {
              entity_id: string;
              updated_at_ms: number;
              detail: { payload: string; message_no: number; topic: string };
            };
            const mqttInputs = inputs.filter((input) =>
              input.brokerHost === entry.brokerHost
              && input.brokerPort === entry.brokerPort
              && input.topic === parsed.entity_id,
            );
            mqttInputs.forEach((input) => {
              try {
                const value = extractValueFromPayload(parsed.detail.payload, input.jsonKey);
                this.setInputValue(input.id, {
                  value,
                  rawPayload: parsed.detail.payload,
                  topic: parsed.entity_id,
                  updatedAtMs: parsed.updated_at_ms,
                  messageNo: Number(parsed.detail.message_no || 0),
                  stale: false,
                });
              } catch {
                this.setInputValue(input.id, {
                  value: parsed.detail.payload,
                  rawPayload: parsed.detail.payload,
                  topic: parsed.entity_id,
                  updatedAtMs: parsed.updated_at_ms,
                  messageNo: Number(parsed.detail.message_no || 0),
                  stale: false,
                });
              }
            });
            this.streamStates[key] = { state: 'open', topics: entry.topics, lastEventAtMs: Date.now(), error: '' };
          } catch {
            this.streamStates[key] = { ...this.streamStates[key], state: 'error', error: 'Runtime-Event ungültig.' };
          }
        });

        brokerStreams.set(key, { signature, source });
      });
    },
    stopAllStreams() {
      brokerStreams.forEach((entry) => entry.source.close());
      brokerStreams.clear();
    },
  },
});
