from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Callable
from urllib import error as urlerror
from urllib import request as urlrequest


LATEST_VERSION_URL = 'https://raw.githubusercontent.com/Blueforcer/awtrix3/main/version'

LatestVersionFetcher = Callable[[], str]
StatsFetcher = Callable[[str], dict[str, Any]]
UpdateTrigger = Callable[[str], dict[str, Any]]


def _clean_version(value: Any) -> str:
    return str(value or '').strip()


def _version_key(value: str) -> tuple[int, ...]:
    parts = re.findall(r'\d+', str(value or ''))
    return tuple(int(part) for part in parts) if parts else (0,)


def _is_newer_version(candidate: str, current: str) -> bool:
    clean_candidate = _clean_version(candidate)
    clean_current = _clean_version(current)
    if not clean_candidate or not clean_current:
        return False
    return _version_key(clean_candidate) > _version_key(clean_current)


def _fetch_latest_version() -> str:
    req = urlrequest.Request(LATEST_VERSION_URL, method='GET')
    with urlrequest.urlopen(req, timeout=5) as resp:
        return resp.read().decode('utf-8', 'replace').strip()


def _fetch_display_stats(ip: str) -> dict[str, Any]:
    req = urlrequest.Request(f'http://{ip}/api/stats', method='GET')
    with urlrequest.urlopen(req, timeout=5) as resp:
        raw = resp.read().decode('utf-8', 'replace')
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError('Display stats are invalid.')
    return parsed


def _trigger_display_update(ip: str) -> dict[str, Any]:
    req = urlrequest.Request(f'http://{ip}/api/doupdate', data=b'', method='POST')
    try:
        with urlrequest.urlopen(req, timeout=10) as resp:
            status_code = int(getattr(resp, 'status', 200) or 200)
            body = resp.read().decode('utf-8', 'replace').strip()
    except urlerror.HTTPError as exc:
        status_code = int(getattr(exc, 'status', exc.code) or exc.code)
        body = exc.read().decode('utf-8', 'replace').strip()
    return {
        'ip': ip,
        'status_code': status_code,
        'body': body,
        'ok': 200 <= status_code < 300,
    }


class DisplayUpdateService:
    def __init__(
        self,
        *,
        latest_version_fetcher: LatestVersionFetcher | None = None,
        stats_fetcher: StatsFetcher | None = None,
        update_trigger: UpdateTrigger | None = None,
        cache_ttl_s: int = 900,
    ) -> None:
        self.latest_version_fetcher = latest_version_fetcher or _fetch_latest_version
        self.stats_fetcher = stats_fetcher or _fetch_display_stats
        self.update_trigger = update_trigger or _trigger_display_update
        self.cache_ttl_s = max(30, int(cache_ttl_s or 900))
        self._lock = threading.Lock()
        self._latest_cache = {
            'version': '',
            'checked_at_ms': 0,
            'error': '',
        }

    def latest_version(self, refresh: bool = False) -> dict[str, Any]:
        now_ms = int(time.time() * 1000)
        with self._lock:
            cached = dict(self._latest_cache)
        if not refresh and cached['version'] and (now_ms - int(cached['checked_at_ms'] or 0)) < (self.cache_ttl_s * 1000):
            return cached

        version = ''
        error = ''
        try:
            version = _clean_version(self.latest_version_fetcher())
            if not version:
                raise RuntimeError('Latest AWTRIX version is empty.')
        except Exception as exc:
            error = str(exc)
            version = _clean_version(cached.get('version'))

        payload = {
            'version': version,
            'checked_at_ms': now_ms,
            'error': error,
        }
        with self._lock:
            self._latest_cache = dict(payload)
        return payload

    def status(self, ip: str, refresh: bool = False) -> dict[str, Any]:
        clean_ip = str(ip or '').strip()
        if not clean_ip:
            raise ValueError('ip is required')

        latest = self.latest_version(refresh=refresh)
        current_version = ''
        app = ''
        error = str(latest.get('error', '') or '')

        try:
            stats = self.stats_fetcher(clean_ip)
            current_version = _clean_version(stats.get('version'))
            app = str(stats.get('app', '') or '').strip()
        except Exception as exc:
            error = f'{error}; {exc}'.strip('; ').strip()

        return {
            'ip': clean_ip,
            'current_version': current_version,
            'latest_version': str(latest.get('version', '') or ''),
            'update_available': _is_newer_version(str(latest.get('version', '') or ''), current_version),
            'app': app,
            'checked_at_ms': int(latest.get('checked_at_ms', int(time.time() * 1000)) or 0),
            'error': error,
        }

    def trigger_update(self, ip: str) -> dict[str, Any]:
        clean_ip = str(ip or '').strip()
        if not clean_ip:
            raise ValueError('ip is required')
        return self.update_trigger(clean_ip)
