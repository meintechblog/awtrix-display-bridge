from __future__ import annotations

import json
import os
import threading
import time
from typing import Any


def _default_payload() -> dict[str, Any]:
    return {
        'version': 1,
        'updated_at': 0,
        'displays': [],
        'inputs': [],
        'bindings': [],
    }


def _sanitize_input(item: dict[str, Any]) -> dict[str, Any]:
    clean = dict(item)
    clean.pop('maxStaleMs', None)
    clean.pop('max_stale_ms', None)
    return clean


class ConfigStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.Lock()

    def load(self) -> dict[str, Any]:
        if not os.path.exists(self.path):
            return _default_payload()

        with self._lock:
            with open(self.path, 'r', encoding='utf-8') as handle:
                raw = json.load(handle)

        payload = _default_payload()
        if isinstance(raw, dict):
            for key in ('version', 'updated_at', 'displays', 'inputs', 'bindings'):
                if key in raw:
                    payload[key] = raw[key]
        payload['inputs'] = [_sanitize_input(item) for item in payload.get('inputs', []) if isinstance(item, dict)]
        return payload

    def replace_config(
        self,
        *,
        displays: list[dict[str, Any]],
        inputs: list[dict[str, Any]],
        bindings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = {
            'version': 1,
            'updated_at': int(time.time()),
            'displays': [dict(item) for item in displays if isinstance(item, dict)],
            'inputs': [_sanitize_input(item) for item in inputs if isinstance(item, dict)],
            'bindings': [dict(item) for item in bindings if isinstance(item, dict)],
        }
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        temp_path = f'{self.path}.tmp'
        with self._lock:
            with open(temp_path, 'w', encoding='utf-8') as handle:
                json.dump(payload, handle, ensure_ascii=True, separators=(',', ':'))
            os.replace(temp_path, self.path)
        return dict(payload)
