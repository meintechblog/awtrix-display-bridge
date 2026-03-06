from __future__ import annotations

from typing import Any


def list_children(topics: list[str], prefix: str = '', query: str = '') -> list[dict[str, Any]]:
    clean_prefix = str(prefix or '').strip().strip('/')
    clean_query = str(query or '').strip().lower()
    base = f'{clean_prefix}/' if clean_prefix else ''
    items: dict[str, dict[str, Any]] = {}

    for raw_topic in topics:
        topic = str(raw_topic or '').strip().strip('/')
        if not topic:
            continue
        if base and not topic.startswith(base):
            continue

        remainder = topic[len(base):] if base else topic
        if not remainder:
            continue

        segment = remainder.split('/', 1)[0]
        path = f'{base}{segment}'.strip('/')
        item = {
            'segment': segment,
            'path': path,
            'kind': 'branch' if '/' in remainder else 'leaf',
        }
        items[path] = item

    results = list(items.values())
    if clean_query:
        results = [
            item for item in results
            if clean_query in item['segment'].lower() or clean_query in item['path'].lower()
        ]

    results.sort(key=lambda item: item['segment'])
    return results
