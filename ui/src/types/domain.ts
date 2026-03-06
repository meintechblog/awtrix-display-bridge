export type SaveState = 'idle' | 'dirty' | 'saving' | 'saved' | 'error';
export type DisplayHealth = 'online' | 'offline' | 'stale' | 'unknown';
export type SkillKind = 'text' | 'mqtt';

export interface DeliveryConfig {
  template: string;
  sendMode: string;
  displayDuration: string;
}

export interface DisplayConfig {
  id: string;
  name: string;
  ip: string;
}

export interface DiscoveryDisplay {
  ip: string;
  name: string;
  version?: string;
  app?: string;
  wifiSignal?: number | null;
  matrix?: boolean | null;
  updatedAtMs: number;
}

export interface TextInputConfig {
  id: string;
  kind: 'text';
  name: string;
  text: string;
  delivery: DeliveryConfig;
}

export interface MqttInputConfig {
  id: string;
  kind: 'mqtt';
  name: string;
  brokerHost: string;
  brokerPort: number;
  topic: string;
  jsonKey: string;
  timeout: number;
  topicSearch: string;
  delivery: DeliveryConfig;
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
  batteryLevel?: number | null;
  batteryRaw?: number | null;
  externalPowerHint?: boolean;
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

export interface DiscoverySnapshot {
  items: DiscoveryDisplay[];
  count: number;
  error: string;
  updated_at_ms: number;
  scan_active: boolean;
}

export interface DisplayUpdateStatus {
  ip: string;
  currentVersion: string;
  latestVersion: string;
  updateAvailable: boolean;
  app: string;
  checkedAtMs: number;
  error: string;
}

export interface DisplayUpdateResult {
  ip: string;
  statusCode: number;
  body: string;
  ok: boolean;
}

export type DisplayUpdateJobPhase =
  | 'queued'
  | 'checking'
  | 'downloading'
  | 'uploading'
  | 'rebooting'
  | 'verifying'
  | 'completed'
  | 'failed';

export interface DisplayUpdateJob {
  jobId: string;
  ip: string;
  phase: DisplayUpdateJobPhase;
  message: string;
  done: boolean;
  ok: boolean;
  result: Record<string, unknown>;
}
