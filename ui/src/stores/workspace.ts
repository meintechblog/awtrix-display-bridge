import { defineStore } from 'pinia';

import { fetchConfig, replaceAutoRoutes, saveConfig } from '../api/client';
import type { AppConfigPayload, BindingConfig, DisplayConfig, InputConfig, MqttInputConfig, SaveState } from '../types/domain';
import { defaultBinding, defaultDisplay, defaultMqttInput, defaultTextInput, normalizeIp, seedWorkspace, DEFAULT_DISPLAY_IP, DEFAULT_STALE_MS } from '../utils/defaults';

let saveTimer: ReturnType<typeof window.setTimeout> | null = null;

function normalizeDisplay(display: Partial<DisplayConfig>, fallbackName: string): DisplayConfig {
  return {
    id: String(display.id || '').trim() || `display-${Math.random().toString(36).slice(2, 8)}`,
    name: String(display.name || '').trim() || fallbackName,
    ip: normalizeIp(String(display.ip || '')) || DEFAULT_DISPLAY_IP,
  };
}

function normalizeInput(input: Partial<InputConfig>, index: number): InputConfig {
  if (input.kind === 'mqtt') {
    return {
      ...defaultMqttInput(`MQTT ${index + 1}`),
      ...input,
      id: String(input.id || '').trim() || `input-${Math.random().toString(36).slice(2, 8)}`,
      name: String(input.name || '').trim() || `MQTT ${index + 1}`,
      brokerHost: normalizeIp(String((input as MqttInputConfig).brokerHost || '')),
      brokerPort: Number((input as MqttInputConfig).brokerPort) || 1883,
      topic: String((input as MqttInputConfig).topic || '').trim(),
      jsonKey: String((input as MqttInputConfig).jsonKey || '').trim(),
      template: String((input as MqttInputConfig).template || '{value}'),
      displayMode: String((input as MqttInputConfig).displayMode || '8'),
      autoMode: String((input as MqttInputConfig).autoMode || 'off'),
      maxStaleMs: String((input as MqttInputConfig).maxStaleMs || DEFAULT_STALE_MS),
      timeout: Number((input as MqttInputConfig).timeout) || 4,
      topicSearch: String((input as MqttInputConfig).topicSearch || ''),
      kind: 'mqtt',
    };
  }

  return {
    ...defaultTextInput(`Text ${index + 1}`),
    ...input,
    id: String(input.id || '').trim() || `input-${Math.random().toString(36).slice(2, 8)}`,
    name: String(input.name || '').trim() || `Text ${index + 1}`,
    text: String((input as { text?: string }).text || ''),
    duration: Math.min(120, Math.max(1, Number((input as { duration?: number }).duration) || 8)),
    kind: 'text',
  };
}

function normalizeBinding(binding: Partial<BindingConfig>, inputId: string, displayIds: string[]): BindingConfig {
  return {
    id: String(binding.id || '').trim() || `binding-${Math.random().toString(36).slice(2, 8)}`,
    inputId,
    displayIds: Array.from(new Set((binding.displayIds || []).map((item) => String(item)).filter(Boolean))).length
      ? Array.from(new Set((binding.displayIds || []).map((item) => String(item)).filter(Boolean)))
      : displayIds,
    enabled: binding.enabled !== false,
  };
}

function sanitizePayload(state: {
  displays: DisplayConfig[];
  inputs: InputConfig[];
  bindings: BindingConfig[];
}): AppConfigPayload {
  return {
    version: 1,
    updated_at: Date.now(),
    displays: state.displays.map((display, index) => normalizeDisplay(display, `Display ${index + 1}`)),
    inputs: state.inputs.map((input, index) => normalizeInput(input, index)),
    bindings: state.bindings.map((binding) => normalizeBinding(binding, binding.inputId, [])),
  };
}

export const useWorkspaceStore = defineStore('workspace', {
  state: () => ({
    displays: [] as DisplayConfig[],
    inputs: [] as InputConfig[],
    bindings: [] as BindingConfig[],
    saveState: 'idle' as SaveState,
    lastSavedAt: 0,
    saveError: '',
    loaded: false,
    loading: false,
  }),
  getters: {
    inputById: (state) => (inputId: string) => state.inputs.find((input) => input.id === inputId),
    displayById: (state) => (displayId: string) => state.displays.find((display) => display.id === displayId),
    bindingByInputId: (state) => (inputId: string) => state.bindings.find((binding) => binding.inputId === inputId),
    assignedDisplayIds() {
      return (inputId: string) => this.bindingByInputId(inputId)?.displayIds || [];
    },
    assignedDisplays() {
      return (inputId: string) => this.assignedDisplayIds(inputId)
        .map((displayId) => this.displayById(displayId))
        .filter((display): display is DisplayConfig => Boolean(display));
    },
    assignedInputs() {
      return (displayId: string) => this.inputs.filter((input) => this.assignedDisplayIds(input.id).includes(displayId));
    },
    mqttInputs: (state) => state.inputs.filter((input): input is MqttInputConfig => input.kind === 'mqtt'),
    saveLabel(state): string {
      if (state.saveState === 'saving') return 'Ungespeichert';
      if (state.saveState === 'error') return 'Speicherfehler';
      return 'Gespeichert';
    },
    hasConfig(state): boolean {
      return state.displays.length > 0 || state.inputs.length > 0;
    },
  },
  actions: {
    applyConfig(payload: AppConfigPayload) {
      const source = payload.displays.length || payload.inputs.length || payload.bindings.length
        ? payload
        : seedWorkspace();

      this.displays = source.displays.map((display, index) => normalizeDisplay(display, `Display ${index + 1}`));
      this.inputs = source.inputs.map((input, index) => normalizeInput(input, index));
      this.bindings = this.inputs.map((input) => {
        const existing = source.bindings.find((binding) => binding.inputId === input.id);
        return normalizeBinding(existing || defaultBinding(input.id, this.displays.slice(0, 1).map((display) => display.id)), input.id, this.displays.slice(0, 1).map((display) => display.id));
      });
    },
    async load() {
      this.loading = true;
      try {
        const payload = await fetchConfig();
        this.applyConfig(payload);
        if (!payload.displays.length && !payload.inputs.length && !payload.bindings.length) {
          await this.saveNow();
        } else {
          this.saveState = 'saved';
          this.lastSavedAt = Date.now();
        }
      } catch (error) {
        this.applyConfig(seedWorkspace());
        this.saveState = 'error';
        this.saveError = error instanceof Error ? error.message : 'Konfiguration konnte nicht geladen werden.';
      } finally {
        this.loading = false;
        this.loaded = true;
      }
    },
    queueSave(delayMs = 320) {
      this.saveState = 'saving';
      this.saveError = '';
      if (saveTimer) {
        window.clearTimeout(saveTimer);
      }
      saveTimer = window.setTimeout(() => {
        saveTimer = null;
        void this.saveNow();
      }, delayMs);
    },
    async saveNow() {
      const payload = sanitizePayload(this);
      try {
        const stored = await saveConfig(payload);
        this.applyConfig(stored);
        this.lastSavedAt = Date.now();
        this.saveState = 'saved';
        this.saveError = '';
        await this.syncAutoRoutes();
      } catch (error) {
        this.saveState = 'error';
        this.saveError = error instanceof Error ? error.message : 'Speichern fehlgeschlagen.';
      }
    },
    async syncAutoRoutes() {
      const routes = this.mqttInputs.flatMap((input) => {
        if (String(input.autoMode || 'off') === 'off') {
          return [];
        }
        return this.assignedDisplays(input.id)
          .filter((display) => display.ip && input.topic && input.brokerHost)
          .map((display) => ({
            id: `${input.id}:${display.id}`,
            title: input.name,
            display_ip: display.ip,
            broker_host: input.brokerHost,
            broker_port: input.brokerPort,
            topic: input.topic,
            json_key: input.jsonKey,
            template: input.template,
            display_mode: input.displayMode,
            auto_mode: input.autoMode,
            max_stale_ms: Number(input.maxStaleMs) || Number(DEFAULT_STALE_MS),
            enabled: true,
          }));
      });

      const baseDisplay = this.displays[0];
      if (!baseDisplay?.ip) {
        return;
      }
      await replaceAutoRoutes(baseDisplay.ip, routes);
    },
    addDisplay() {
      this.displays.push(defaultDisplay(`Display ${this.displays.length + 1}`));
      this.queueSave();
    },
    updateDisplay(displayId: string, patch: Partial<DisplayConfig>) {
      const index = this.displays.findIndex((display) => display.id === displayId);
      if (index < 0) {
        return;
      }
      this.displays[index] = normalizeDisplay({ ...this.displays[index], ...patch }, this.displays[index].name);
      this.queueSave();
    },
    removeDisplay(displayId: string) {
      if (this.displays.length <= 1) {
        return;
      }
      this.displays = this.displays.filter((display) => display.id !== displayId);
      this.bindings = this.bindings.map((binding) => ({
        ...binding,
        displayIds: binding.displayIds.filter((id) => id !== displayId),
      }));
      this.queueSave();
    },
    addInput(kind: 'text' | 'mqtt') {
      const input = kind === 'mqtt'
        ? defaultMqttInput(`MQTT ${this.inputs.filter((item) => item.kind === 'mqtt').length + 1}`)
        : defaultTextInput(`Text ${this.inputs.filter((item) => item.kind === 'text').length + 1}`);
      this.inputs.unshift(input);
      this.bindings.unshift(defaultBinding(input.id, this.displays.slice(0, 1).map((display) => display.id)));
      this.queueSave();
      return input.id;
    },
    updateInput(inputId: string, patch: Partial<InputConfig>) {
      const index = this.inputs.findIndex((input) => input.id === inputId);
      if (index < 0) {
        return;
      }
      const merged = { ...this.inputs[index], ...patch } as InputConfig;
      this.inputs[index] = normalizeInput(merged, index);
      this.queueSave();
    },
    removeInput(inputId: string) {
      this.inputs = this.inputs.filter((input) => input.id !== inputId);
      this.bindings = this.bindings.filter((binding) => binding.inputId !== inputId);
      this.queueSave();
    },
    toggleDisplayAssignment(inputId: string, displayId: string) {
      const binding = this.bindingByInputId(inputId);
      if (!binding) {
        this.bindings.push(defaultBinding(inputId, [displayId]));
        this.queueSave();
        return;
      }
      const next = binding.displayIds.includes(displayId)
        ? binding.displayIds.filter((id) => id !== displayId)
        : [...binding.displayIds, displayId];
      binding.displayIds = next;
      this.queueSave();
    },
  },
});
