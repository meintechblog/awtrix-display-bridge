from __future__ import annotations

import ipaddress
import json
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Optional
from urllib import error as urlerror
from urllib import request as urlrequest


InterfaceProvider = Callable[[], list[str]]
ProbeFunc = Callable[[str], Optional[dict[str, Any]]]


def _default_interface_provider() -> list[str]:
    try:
        raw = subprocess.check_output(
            ['ip', '-j', '-4', 'addr', 'show', 'up', 'scope', 'global'],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return []

    try:
        parsed = json.loads(raw)
    except Exception:
        return []

    networks: list[str] = []
    for iface in parsed if isinstance(parsed, list) else []:
        for addr_info in iface.get('addr_info', []) if isinstance(iface, dict) else []:
            local = str(addr_info.get('local', '')).strip()
            prefixlen = addr_info.get('prefixlen')
            if not local or not isinstance(prefixlen, int):
                continue
            try:
                network = ipaddress.ip_interface(f'{local}/{prefixlen}').network
            except Exception:
                continue
            if isinstance(network, ipaddress.IPv4Network) and network.is_private:
                networks.append(str(network))
    return sorted(set(networks))


def _normalize_probe(ip: str, payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get('name') or payload.get('hostname') or payload.get('device') or 'AWTRIX').strip() or 'AWTRIX'
    version = payload.get('version')
    app = payload.get('app')
    wifi_signal = payload.get('wifi_signal')
    matrix = payload.get('matrix')
    return {
        'ip': ip,
        'name': name,
        'version': str(version).strip() if isinstance(version, (str, int, float)) else '',
        'app': str(app).strip() if isinstance(app, (str, int, float)) else '',
        'wifiSignal': wifi_signal if isinstance(wifi_signal, (int, float)) else None,
        'matrix': matrix if isinstance(matrix, bool) else None,
        'updatedAtMs': int(time.time() * 1000),
    }


def _default_probe(ip: str) -> Optional[dict[str, Any]]:
    req = urlrequest.Request(f'http://{ip}/api/stats', method='GET')
    try:
        with urlrequest.urlopen(req, timeout=0.8) as resp:
            if getattr(resp, 'status', 200) != 200:
                return None
            raw = resp.read().decode('utf-8', 'replace')
    except (TimeoutError, urlerror.URLError, urlerror.HTTPError, OSError):
        return None

    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    if 'version' not in parsed and 'app' not in parsed and 'matrix' not in parsed:
        return None
    return _normalize_probe(ip, parsed)


class DisplayDiscoveryService:
    def __init__(
        self,
        interval_s: int = 30,
        interface_provider: InterfaceProvider | None = None,
        probe: ProbeFunc | None = None,
    ) -> None:
        self.interval_s = max(5, int(interval_s or 30))
        self.interface_provider = interface_provider or _default_interface_provider
        self.probe = probe or _default_probe
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name='awtrix-display-discovery', daemon=True)
        self._cache: dict[str, Any] = {
            'items': [],
            'count': 0,
            'error': '',
            'updated_at_ms': 0,
            'scan_active': False,
        }

    @staticmethod
    def _iter_hosts(networks: list[str]) -> list[str]:
        hosts: list[str] = []
        for cidr in networks:
            try:
                network = ipaddress.ip_network(cidr, strict=False)
            except Exception:
                continue
            if not isinstance(network, ipaddress.IPv4Network) or not network.is_private:
                continue
            if network.num_addresses > 512:
                continue
            hosts.extend(str(host) for host in network.hosts())
        return sorted(set(hosts))

    def _update_cache(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._cache = {
                'items': [dict(item) for item in payload.get('items', []) if isinstance(item, dict)],
                'count': int(payload.get('count', 0) or 0),
                'error': str(payload.get('error', '') or ''),
                'updated_at_ms': int(payload.get('updated_at_ms', 0) or 0),
                'scan_active': bool(payload.get('scan_active', False)),
            }

    def run_scan(self, excluded_ips: Optional[set[str]] = None) -> dict[str, Any]:
        excluded = {str(item).strip() for item in (excluded_ips or set()) if str(item).strip()}
        networks = self.interface_provider()
        if not networks:
            return {
                'items': [],
                'count': 0,
                'error': 'Keine privaten Subnetze gefunden.',
                'updated_at_ms': int(time.time() * 1000),
                'scan_active': False,
            }

        hosts = [ip for ip in self._iter_hosts(networks) if ip not in excluded]
        items: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=24) as pool:
            futures = {pool.submit(self.probe, ip): ip for ip in hosts}
            for future in as_completed(futures):
                try:
                    result = future.result()
                except Exception:
                    continue
                if not isinstance(result, dict):
                    continue
                ip = str(result.get('ip', '')).strip() or futures[future]
                if not ip or ip in excluded:
                    continue
                normalized = {
                    'ip': ip,
                    'name': str(result.get('name', 'AWTRIX')).strip() or 'AWTRIX',
                    'version': str(result.get('version', '')).strip(),
                    'app': str(result.get('app', '')).strip(),
                    'wifiSignal': result.get('wifiSignal') if isinstance(result.get('wifiSignal'), (int, float)) else None,
                    'matrix': result.get('matrix') if isinstance(result.get('matrix'), bool) else None,
                    'updatedAtMs': int(result.get('updatedAtMs', int(time.time() * 1000)) or 0),
                }
                items.append(normalized)

        items.sort(key=lambda item: (item.get('name', ''), item.get('ip', '')))
        return {
            'items': items,
            'count': len(items),
            'error': '',
            'updated_at_ms': int(time.time() * 1000),
            'scan_active': False,
        }

    def snapshot(self, excluded_ips: set[str]) -> dict[str, Any]:
        excluded = {str(item).strip() for item in excluded_ips if str(item).strip()}
        with self._lock:
            cache = dict(self._cache)
            items = [dict(item) for item in cache.get('items', []) if isinstance(item, dict)]
        filtered = [item for item in items if str(item.get('ip', '')).strip() not in excluded]
        cache['items'] = filtered
        cache['count'] = len(filtered)
        return cache

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._update_cache({**self.snapshot(set()), 'scan_active': True})
            try:
                payload = self.run_scan()
            except Exception as exc:
                payload = {
                    'items': [],
                    'count': 0,
                    'error': str(exc),
                    'updated_at_ms': int(time.time() * 1000),
                    'scan_active': False,
                }
            self._update_cache(payload)
            if self._stop.wait(self.interval_s):
                break

    def start(self) -> None:
        if self._thread.is_alive():
            return
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1.5)
