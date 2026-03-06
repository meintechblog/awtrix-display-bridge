export type SaveState = 'idle' | 'dirty' | 'saving' | 'saved' | 'error';
export type DisplayHealth = 'online' | 'offline' | 'stale' | 'unknown';
export type InputKind = 'text' | 'mqtt';

export interface DisplayConfig {
  id: string;
  name: string;
  ip: string;
}

export interface TextInputConfig {
  id: string;
  kind: 'text';
  name: string;
  text: string;
  duration: number;
}

export interface MqttInputConfig {
  id: string;
  kind: 'mqtt';
  name: string;
  brokerHost: string;
  brokerPort: number;
  topic: string;
  jsonKey: string;
  template: string;
  displayMode: string;
  autoMode: string;
  timeout: number;
  topicSearch: string;
}

export type InputConfig = TextInputConfig | MqttInputConfig;

export interface BindingConfig {
  id: string;
  inputId: string;
  displayIds: string[];
  enabled: boolean;
}

export interface AppConfigPayload {
  version: number;
  updated_at: number;
  displays: DisplayConfig[];
  inputs: InputConfig[];
  bindings: BindingConfig[];
}

export interface DashboardSummary {
  displays: number;
  online: number;
  offline: number;
  stale: number;
  inputs: number;
  bindings: number;
  liveBrokers: number;
}

export interface DisplayRuntimeState {
  state: DisplayHealth;
  updatedAtMs: number;
  version?: string;
  app?: string;
  wifiSignal?: number | null;
  matrix?: boolean | null;
  error?: string;
}

export interface InputRuntimeValue {
  value: string;
  rawPayload: string;
  topic: string;
  updatedAtMs: number;
  messageNo: number;
  stale: boolean;
}

export interface TopicBrowserItem {
  segment: string;
  path: string;
  kind: 'branch' | 'leaf';
}

export interface TopicDetail {
  topic: string;
  rawPayload: string;
  jsonKeys: string[];
  previewValue: string;
}
