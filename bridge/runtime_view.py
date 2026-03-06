from __future__ import annotations

import time
from typing import Any


def normalize_runtime_event(
    *,
    event_type: str,
    entity: str,
    entity_id: str,
    state: str,
    updated_at_ms: int,
    detail: dict[str, Any],
) -> dict[str, Any]:
    return {
        'type': str(event_type or '').strip(),
        'entity': str(entity or '').strip(),
        'entity_id': str(entity_id or '').strip(),
        'state': str(state or '').strip(),
        'updated_at_ms': int(updated_at_ms or 0),
        'detail': dict(detail or {}),
    }


def build_dashboard_summary(config: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    displays = [item for item in config.get('displays', []) if isinstance(item, dict)]
    inputs = [item for item in config.get('inputs', []) if isinstance(item, dict)]
    bindings = [item for item in config.get('bindings', []) if isinstance(item, dict)]
    display_status = runtime.get('display_status', {})
    if not isinstance(display_status, dict):
        display_status = {}

    online = 0
    offline = 0
    for display in displays:
        state = str(display_status.get(str(display.get('id', '')), {}).get('state', '')).strip().lower()
        if state == 'online':
            online += 1
        elif state == 'offline':
            offline += 1

    return {
        'totals': {
            'displays': len(displays),
            'online': online,
            'offline': offline,
            'unknown': max(0, len(displays) - online - offline),
            'inputs': len(inputs),
            'bindings': len(bindings),
            'live_brokers': int(runtime.get('live_brokers', 0) or 0),
            'auto_routes': int(runtime.get('auto_routes', 0) or 0),
        },
        'updated_at_ms': int(runtime.get('updated_at_ms', int(time.time() * 1000)) or 0),
    }
