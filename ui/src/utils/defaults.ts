import type { AppConfigPayload, BindingConfig, DisplayConfig, MqttInputConfig, TextInputConfig } from '../types/domain';

export const DEFAULT_DISPLAY_IP = '192.168.3.126';
export const DEFAULT_MQTT_BROKER = '192.168.3.8';
export const DEFAULT_MQTT_TOPIC = 'trading-deluxxe/webapp/status/balance';
export const LEGACY_CUSTOM_APP = 'webtext';

export function normalizeIp(value: string): string {
  return String(value || '')
    .trim()
    .replace(/^https?:\/\//i, '')
    .replace(/\/+$/, '');
}

export function uid(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 8)}${Date.now().toString(36)}`;
}

export function defaultDisplay(name = 'Display 1', ip = DEFAULT_DISPLAY_IP): DisplayConfig {
  return {
    id: uid('display'),
    name,
    ip,
  };
}

export function defaultTextInput(name = 'Text'): TextInputConfig {
  return {
    id: uid('input'),
    kind: 'text',
    name,
    text: '',
    duration: 8,
  };
}

export function defaultMqttInput(name = 'MQTT'): MqttInputConfig {
  return {
    id: uid('input'),
    kind: 'mqtt',
    name,
    brokerHost: DEFAULT_MQTT_BROKER,
    brokerPort: 1883,
    topic: '',
    jsonKey: '',
    template: '{value}',
    displayMode: '8',
    autoMode: 'off',
    timeout: 4,
    topicSearch: '',
  };
}

export function presetBalanceInput(): MqttInputConfig {
  return {
    ...defaultMqttInput('MQTT Balance'),
    id: 'preset-mqtt-balance',
    topic: DEFAULT_MQTT_TOPIC,
    template: 'Balance: {value}',
  };
}

export function defaultBinding(inputId: string, displayIds: string[]): BindingConfig {
  return {
    id: uid('binding'),
    inputId,
    displayIds,
    enabled: true,
  };
}

export function seedWorkspace(): AppConfigPayload {
  const display = defaultDisplay();
  const textInput = defaultTextInput();
  const mqttInput = presetBalanceInput();
  return {
    version: 1,
    updated_at: 0,
    displays: [display],
    inputs: [mqttInput, textInput],
    bindings: [
      defaultBinding(mqttInput.id, [display.id]),
      defaultBinding(textInput.id, [display.id]),
    ],
  };
}
