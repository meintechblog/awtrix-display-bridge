from __future__ import annotations

from typing import Any


def _dict_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, dict)]


def config_payload(data: dict[str, Any]) -> dict[str, Any]:
    return {
        'version': int(data.get('version', 1) or 1),
        'updated_at': int(data.get('updated_at', 0) or 0),
        'displays': _dict_items(data.get('displays', [])),
        'inputs': _dict_items(data.get('inputs', [])),
        'bindings': _dict_items(data.get('bindings', [])),
    }


def collection_payload(data: dict[str, Any], key: str) -> dict[str, Any]:
    payload = config_payload(data)
    return {
        'items': list(payload.get(key, [])),
        'count': len(payload.get(key, [])),
    }
