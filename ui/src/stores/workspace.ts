import { defineStore } from 'pinia';

import { fetchConfig, replaceAutoRoutes, saveConfig } from '../api/client';
import type { AppConfigPayload, BindingConfig, DiscoveryDisplay, DisplayConfig, InputConfig, MqttInputConfig, SaveState } from '../types/domain';
import { defaultBinding, defaultDisplay, defaultMqttInput, defaultTextInput, normalizeIp, seedWorkspace, DEFAULT_DISPLAY_IP } from '../utils/defaults';

type ComparableConfig = Omit<AppConfigPayload, 'updated_at'>;

function cloneComparable<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

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
  const uniqueDisplayIds = Array.from(new Set((binding.displayIds || []).map((item) => String(item)).filter(Boolean)));
  return {
    id: String(binding.id || '').trim() || `binding-${Math.random().toString(36).slice(2, 8)}`,
    inputId,
    displayIds: uniqueDisplayIds.length ? uniqueDisplayIds : displayIds,
    enabled: binding.enabled !== false,
  };
}

function buildComparableConfig(state: {
  displays: DisplayConfig[];
  inputs: InputConfig[];
  bindings: BindingConfig[];
}): ComparableConfig {
  return {
    version: 1,
    displays: state.displays.map((display, index) => normalizeDisplay(display, `Display ${index + 1}`)),
    inputs: state.inputs.map((input, index) => normalizeInput(input, index)),
    bindings: state.bindings.map((binding) => normalizeBinding(binding, binding.inputId, [])),
  };
}

function buildSavePayload(state: {
  displays: DisplayConfig[];
  inputs: InputConfig[];
  bindings: BindingConfig[];
}): AppConfigPayload {
  return {
    ...buildComparableConfig(state),
    updated_at: Date.now(),
  };
}

function comparableSignature(config: ComparableConfig): string {
  return JSON.stringify(config);
}

function resolveScopedState(isDirty: boolean, globalState: SaveState): SaveState {
  if (!isDirty) {
    return 'saved';
  }
  if (globalState === 'saving') {
    return 'saving';
  }
  if (globalState === 'error') {
    return 'error';
  }
  return 'dirty';
}

export const useWorkspaceStore = defineStore('workspace', {
  state: () => ({
    displays: [] as DisplayConfig[],
    inputs: [] as InputConfig[],
    bindings: [] as BindingConfig[],
    persistedConfig: null as ComparableConfig | null,
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
    currentComparableConfig(state): ComparableConfig {
      return buildComparableConfig(state);
    },
    hasUnsavedChanges(): boolean {
      if (!this.persistedConfig) {
        return this.inputs.length > 0 || this.displays.length > 0 || this.bindings.length > 0;
      }
      return comparableSignature(this.currentComparableConfig) !== comparableSignature(this.persistedConfig);
    },
    canSave(): boolean {
      return this.saveState !== 'saving' && this.hasUnsavedChanges;
    },
    canDiscard(): boolean {
      return this.saveState !== 'saving' && this.hasUnsavedChanges;
    },
    saveLabel(state): string {
      if (state.saveState === 'dirty') return 'Ungespeichert';
      if (state.saveState === 'saving') return 'Speichert...';
      if (state.saveState === 'error') return 'Speicherfehler';
      return 'Gespeichert';
    },
    saveNote(): string {
      if (this.saveState === 'error') {
        return this.saveError || 'Speichern fehlgeschlagen.';
      }
      if (this.hasUnsavedChanges) {
        return 'Änderungen bleiben lokal, bis du speicherst.';
      }
      if (this.lastSavedAt > 0) {
        return `Letzte Speicherung ${new Date(this.lastSavedAt).toLocaleTimeString('de-DE')}`;
      }
      return 'Keine Änderungen offen.';
    },
    inputIsDirty() {
      return (inputId: string) => {
        const currentInput = this.inputById(inputId);
        const currentBinding = this.bindingByInputId(inputId);
        const persistedInput = this.persistedConfig?.inputs.find((input) => input.id === inputId);
        const persistedBinding = this.persistedConfig?.bindings.find((binding) => binding.inputId === inputId);

        const current = currentInput
          ? {
              input: normalizeInput(currentInput, this.inputs.findIndex((input) => input.id === inputId)),
              binding: normalizeBinding(currentBinding || { inputId, displayIds: [] }, inputId, []),
            }
          : null;
        const persisted = persistedInput
          ? {
              input: normalizeInput(persistedInput, this.persistedConfig?.inputs.findIndex((input) => input.id === inputId) ?? 0),
              binding: normalizeBinding(persistedBinding || { inputId, displayIds: [] }, inputId, []),
            }
          : null;

        return JSON.stringify(current) !== JSON.stringify(persisted);
      };
    },
    inputSaveState() {
      return (inputId: string) => resolveScopedState(this.inputIsDirty(inputId), this.saveState);
    },
    inputSaveLabel() {
      return (inputId: string) => {
        const state = this.inputSaveState(inputId);
        if (state === 'dirty') return 'Ungespeichert';
        if (state === 'saving') return 'Speichert...';
        if (state === 'error') return 'Speicherfehler';
        return 'Gespeichert';
      };
    },
    hasConfig(state): boolean {
      return state.displays.length > 0 || state.inputs.length > 0;
    },
  },
  actions: {
    setWorkingConfig(payload: AppConfigPayload | ComparableConfig) {
      const source = payload.displays.length || payload.inputs.length || payload.bindings.length
        ? payload
        : seedWorkspace();

      this.displays = source.displays.map((display, index) => normalizeDisplay(display, `Display ${index + 1}`));
      this.inputs = source.inputs.map((input, index) => normalizeInput(input, index));
      this.bindings = this.inputs.map((input) => {
        const existing = source.bindings.find((binding) => binding.inputId === input.id);
        return normalizeBinding(
          existing || defaultBinding(input.id, this.displays.slice(0, 1).map((display) => display.id)),
          input.id,
          this.displays.slice(0, 1).map((display) => display.id),
        );
      });
    },
    commitPersistedConfig(updatedAt = Date.now()) {
      this.persistedConfig = cloneComparable(buildComparableConfig(this));
      this.lastSavedAt = updatedAt;
    },
    refreshSaveState(clearError = true) {
      if (this.hasUnsavedChanges) {
        if (clearError) {
          this.saveError = '';
        }
        this.saveState = 'dirty';
        return;
      }
      if (clearError) {
        this.saveError = '';
      }
      this.saveState = 'saved';
    },
    async load() {
      this.loading = true;
      try {
        const payload = await fetchConfig();
        if (!payload.displays.length && !payload.inputs.length && !payload.bindings.length) {
          this.setWorkingConfig(seedWorkspace());
          await this.saveNow();
        } else {
          this.setWorkingConfig(payload);
          this.commitPersistedConfig(payload.updated_at || Date.now());
          this.saveState = 'saved';
          this.saveError = '';
        }
      } catch (error) {
        this.setWorkingConfig(seedWorkspace());
        this.persistedConfig = null;
        this.saveState = 'error';
        this.saveError = error instanceof Error ? error.message : 'Konfiguration konnte nicht geladen werden.';
      } finally {
        this.loading = false;
        this.loaded = true;
      }
    },
    async saveNow() {
      if (!this.hasUnsavedChanges && this.persistedConfig) {
        return;
      }

      const payload = buildSavePayload(this);
      this.saveState = 'saving';
      this.saveError = '';

      try {
        const stored = await saveConfig(payload);
        this.setWorkingConfig(stored);
        this.commitPersistedConfig(stored.updated_at || Date.now());
      } catch (error) {
        this.saveState = 'error';
        this.saveError = error instanceof Error ? error.message : 'Speichern fehlgeschlagen.';
        return;
      }

      try {
        await this.syncAutoRoutes();
        this.saveState = 'saved';
        this.saveError = '';
      } catch (error) {
        this.saveState = 'error';
        this.saveError = error instanceof Error ? error.message : 'Auto-Routen konnten nicht synchronisiert werden.';
      }
    },
    discardChanges() {
      if (!this.persistedConfig) {
        return;
      }
      this.setWorkingConfig(this.persistedConfig);
      this.saveState = 'saved';
      this.saveError = '';
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
      this.refreshSaveState();
    },
    adoptDiscoveredDisplay(discovery: DiscoveryDisplay) {
      const ip = normalizeIp(String(discovery.ip || ''));
      if (!ip || this.displays.some((display) => display.ip === ip)) {
        return;
      }
      const nextName = String(discovery.name || '').trim() || `Display ${this.displays.length + 1}`;
      this.displays.push(defaultDisplay(nextName, ip));
      this.refreshSaveState();
    },
    updateDisplay(displayId: string, patch: Partial<DisplayConfig>) {
      const index = this.displays.findIndex((display) => display.id === displayId);
      if (index < 0) {
        return;
      }
      this.displays[index] = normalizeDisplay({ ...this.displays[index], ...patch }, this.displays[index].name);
      this.refreshSaveState();
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
      this.refreshSaveState();
    },
    addInput(kind: 'text' | 'mqtt') {
      const input = kind === 'mqtt'
        ? defaultMqttInput(`MQTT ${this.inputs.filter((item) => item.kind === 'mqtt').length + 1}`)
        : defaultTextInput(`Text ${this.inputs.filter((item) => item.kind === 'text').length + 1}`);
      this.inputs.unshift(input);
      this.bindings.unshift(defaultBinding(input.id, this.displays.slice(0, 1).map((display) => display.id)));
      this.refreshSaveState();
      return input.id;
    },
    updateInput(inputId: string, patch: Partial<InputConfig>) {
      const index = this.inputs.findIndex((input) => input.id === inputId);
      if (index < 0) {
        return;
      }
      const merged = { ...this.inputs[index], ...patch } as InputConfig;
      this.inputs[index] = normalizeInput(merged, index);
      this.refreshSaveState();
    },
    removeInput(inputId: string) {
      this.inputs = this.inputs.filter((input) => input.id !== inputId);
      this.bindings = this.bindings.filter((binding) => binding.inputId !== inputId);
      this.refreshSaveState();
    },
    toggleDisplayAssignment(inputId: string, displayId: string) {
      const binding = this.bindingByInputId(inputId);
      if (!binding) {
        this.bindings.push(defaultBinding(inputId, [displayId]));
        this.refreshSaveState();
        return;
      }
      const next = binding.displayIds.includes(displayId)
        ? binding.displayIds.filter((id) => id !== displayId)
        : [...binding.displayIds, displayId];
      binding.displayIds = next;
      this.refreshSaveState();
    },
  },
});
