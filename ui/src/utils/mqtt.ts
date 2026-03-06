export function splitTopic(topic: string): string[] {
  return String(topic || '')
    .split('/')
    .map((segment) => segment.trim())
    .filter(Boolean);
}

export function extractJsonKeys(rawPayload: string): string[] {
  try {
    const parsed = JSON.parse(String(rawPayload || ''));
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return [];
    }
    return Object.keys(parsed).sort();
  } catch {
    return [];
  }
}

export function pathValue(obj: unknown, path: string): unknown {
  if (!path) {
    return obj;
  }
  return String(path)
    .split('.')
    .map((part) => part.trim())
    .filter(Boolean)
    .reduce<unknown>((current, part) => {
      if (current === null || current === undefined) {
        return undefined;
      }
      if (Array.isArray(current) && /^\d+$/.test(part)) {
        return current[Number(part)];
      }
      if (typeof current === 'object') {
        return (current as Record<string, unknown>)[part];
      }
      return undefined;
    }, obj);
}

export function extractValueFromPayload(rawPayload: string, keyPath: string): string {
  const cleanKey = String(keyPath || '').trim();
  if (!cleanKey) {
    return String(rawPayload || '');
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(String(rawPayload || ''));
  } catch {
    throw new Error('Payload ist kein JSON, aber ein JSON-Key wurde gesetzt.');
  }

  const selected = pathValue(parsed, cleanKey);
  if (selected === undefined) {
    throw new Error(`JSON-Key '${cleanKey}' nicht gefunden.`);
  }
  if (selected && typeof selected === 'object') {
    return JSON.stringify(selected);
  }
  return String(selected);
}

export function formatTemplate(template: string, value: string): string {
  const cleanTemplate = String(template || '').trim() || '{value}';
  return cleanTemplate.includes('{value}')
    ? cleanTemplate.replaceAll('{value}', value)
    : `${cleanTemplate} ${value}`.trim();
}

export function displayModeSeconds(mode: string): number | null {
  const clean = String(mode || '').trim().toLowerCase();
  if (clean === 'until-change') {
    return null;
  }
  const seconds = Number(clean);
  if (!Number.isFinite(seconds)) {
    return 8;
  }
  return Math.min(120, Math.max(1, seconds));
}
