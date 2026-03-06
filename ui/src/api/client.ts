import type {
  AppConfigPayload,
  DiscoverySnapshot,
  DisplayUpdateJob,
  DisplayUpdateResult,
  DisplayUpdateStatus,
  TopicBrowserItem,
} from '../types/domain';
import { LEGACY_CUSTOM_APP } from '../utils/defaults';

type JsonBody = Record<string, unknown>;

function timeoutFetch(url: string, options: RequestInit = {}, timeoutMs = 10000): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...options, signal: controller.signal }).finally(() => {
    window.clearTimeout(timer);
  });
}

function bridgeBaseUrl(): string {
  return `${window.location.protocol}//${window.location.hostname}:8090`;
}

function awtrixBaseUrl(displayIp: string): string {
  return `${window.location.protocol}//${displayIp}`;
}

async function parseJson<T>(response: Response): Promise<T> {
  const data = await response.json();
  return data as T;
}

async function bridgeRequest<T>(
  method: 'GET' | 'POST' | 'PUT',
  path: string,
  payload?: JsonBody,
  params?: URLSearchParams,
  timeoutMs = 12000,
): Promise<T> {
  const suffix = params?.toString() ? `?${params.toString()}` : '';
  const response = await timeoutFetch(`${bridgeBaseUrl()}${path}${suffix}`, {
    method,
    headers: payload ? { 'Content-Type': 'application/json' } : undefined,
    body: payload ? JSON.stringify(payload) : undefined,
  }, timeoutMs);

  const body = await parseJson<{ ok: boolean; result: T; error?: string }>(response);
  if (!response.ok || !body.ok) {
    throw new Error(body.error || `Bridge request failed (${response.status})`);
  }
  return body.result;
}

async function awtrixRequest(
  displayIp: string,
  path: string,
  method: 'GET' | 'POST' = 'GET',
  payload?: JsonBody,
  rawBody?: string,
  timeoutMs = 8000,
): Promise<Response> {
  const response = await timeoutFetch(`${awtrixBaseUrl(displayIp)}${path}`, {
    method,
    headers: payload ? { 'Content-Type': 'application/json' } : undefined,
    body: payload ? JSON.stringify(payload) : rawBody,
  }, timeoutMs);
  if (!response.ok) {
    throw new Error(`Display request failed (${response.status})`);
  }
  return response;
}

export function buildLivePreviewUrl(displayIp: string): string {
  return `/live.html?ip=${encodeURIComponent(displayIp)}`;
}

export function buildDisplayUrl(displayIp: string): string {
  return awtrixBaseUrl(displayIp);
}

export async function fetchConfig(): Promise<AppConfigPayload> {
  return bridgeRequest<AppConfigPayload>('GET', '/api/config');
}

export async function fetchDiscoveredDisplays(refresh = false): Promise<DiscoverySnapshot> {
  const params = new URLSearchParams();
  if (refresh) {
    params.set('refresh', '1');
  }
  return bridgeRequest<DiscoverySnapshot>('GET', '/api/discovery/displays', undefined, params);
}

export async function fetchDisplayUpdateStatus(displayIp: string, refresh = false): Promise<DisplayUpdateStatus> {
  const params = new URLSearchParams({ ip: displayIp });
  if (refresh) {
    params.set('refresh', '1');
  }
  const result = await bridgeRequest<{
    ip: string;
    current_version: string;
    latest_version: string;
    update_available: boolean;
    app: string;
    checked_at_ms: number;
    error: string;
  }>('GET', '/api/display/update-status', undefined, params);

  return {
    ip: result.ip,
    currentVersion: result.current_version || '',
    latestVersion: result.latest_version || '',
    updateAvailable: Boolean(result.update_available),
    app: result.app || '',
    checkedAtMs: Number(result.checked_at_ms || 0),
    error: result.error || '',
  };
}

export async function triggerDisplayUpdate(displayIp: string): Promise<DisplayUpdateResult> {
  const result = await bridgeRequest<{
    ip: string;
    status_code: number;
    body: string;
    ok: boolean;
  }>('POST', '/api/display/update', { ip: displayIp });

  return {
    ip: result.ip,
    statusCode: Number(result.status_code || 0),
    body: result.body || '',
    ok: Boolean(result.ok),
  };
}

export async function startDisplayUpdateJob(displayIp: string): Promise<DisplayUpdateJob> {
  const result = await bridgeRequest<{
    job_id: string;
    ip: string;
    phase: DisplayUpdateJob['phase'];
    message: string;
    done: boolean;
    ok: boolean;
    result: Record<string, unknown>;
  }>('POST', '/api/display/update/start', { ip: displayIp }, undefined, 4000);

  return {
    jobId: result.job_id,
    ip: result.ip,
    phase: result.phase,
    message: result.message || '',
    done: Boolean(result.done),
    ok: Boolean(result.ok),
    result: result.result || {},
  };
}

export async function fetchDisplayUpdateJob(jobId: string): Promise<DisplayUpdateJob> {
  const params = new URLSearchParams({ id: jobId });
  const result = await bridgeRequest<{
    job_id: string;
    ip: string;
    phase: DisplayUpdateJob['phase'];
    message: string;
    done: boolean;
    ok: boolean;
    result: Record<string, unknown>;
  }>('GET', '/api/display/update/job', undefined, params, 4000);

  return {
    jobId: result.job_id,
    ip: result.ip,
    phase: result.phase,
    message: result.message || '',
    done: Boolean(result.done),
    ok: Boolean(result.ok),
    result: result.result || {},
  };
}

export async function saveConfig(payload: AppConfigPayload): Promise<AppConfigPayload> {
  return bridgeRequest<AppConfigPayload>('PUT', '/api/config', payload as unknown as JsonBody);
}

export async function replaceAutoRoutes(displayIp: string, routes: JsonBody[]): Promise<{ count: number }> {
  return bridgeRequest<{ count: number }>('POST', '/auto/routes/replace', {
    display_ip: displayIp,
    routes,
  });
}

export async function browseTopics(
  brokerHost: string,
  brokerPort: number,
  prefix = '',
  query = '',
): Promise<{ count: number; items: TopicBrowserItem[] }> {
  const params = new URLSearchParams({
    broker_host: brokerHost,
    broker_port: String(brokerPort),
    prefix,
    query,
  });
  return bridgeRequest('GET', '/api/topics/browser', undefined, params);
}

export async function syncTopics(
  brokerHost: string,
  brokerPort: number,
  timeoutS = 12,
): Promise<{ count: number }> {
  return bridgeRequest('POST', '/mqtt/topics/sync', {
    broker_host: brokerHost,
    broker_port: brokerPort,
    timeout_s: timeoutS,
    max_topics: 60000,
  }, undefined, timeoutS * 1000 + 5000);
}

export async function fetchTopicValue(
  brokerHost: string,
  brokerPort: number,
  topic: string,
  timeoutS = 4,
): Promise<{ payload: string; message_no: number; received_at_ms: number; stale: boolean }> {
  const params = new URLSearchParams({
    broker_host: brokerHost,
    broker_port: String(brokerPort),
    topic,
    timeout_s: String(timeoutS),
  });
  return bridgeRequest('GET', '/api/topics/value', undefined, params, timeoutS * 1000 + 5000);
}

export async function fetchDisplayStats(displayIp: string): Promise<Record<string, unknown>> {
  const response = await awtrixRequest(displayIp, '/api/stats');
  return parseJson<Record<string, unknown>>(response);
}

export async function sendNotification(
  displayIp: string,
  payload: JsonBody,
): Promise<void> {
  await awtrixRequest(displayIp, '/api/notify', 'POST', payload);
}

export async function clearDisplayContent(displayIp: string): Promise<void> {
  await awtrixRequest(displayIp, '/api/notify/dismiss', 'POST', undefined, '');
  await awtrixRequest(
    displayIp,
    `/api/custom?name=${encodeURIComponent(LEGACY_CUSTOM_APP)}`,
    'POST',
    undefined,
    '',
  );
  await sendNotification(displayIp, {
    text: ' ',
    background: '#000000',
    noScroll: true,
    duration: 1,
    stack: false,
  });
  await new Promise((resolve) => window.setTimeout(resolve, 1100));
  await awtrixRequest(displayIp, '/api/notify/dismiss', 'POST', undefined, '');
}
