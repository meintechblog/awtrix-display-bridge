from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Callable
from urllib import error as urlerror
from urllib import request as urlrequest


LATEST_VERSION_URL = 'https://raw.githubusercontent.com/Blueforcer/awtrix3/main/version'
LATEST_RELEASE_URL = 'https://api.github.com/repos/Blueforcer/awtrix3/releases/latest'

LatestVersionFetcher = Callable[[], str]
ReleaseFetcher = Callable[[], dict[str, Any]]
StatsFetcher = Callable[[str], dict[str, Any]]
UpdateTrigger = Callable[[str], dict[str, Any]]
FirmwareDownloader = Callable[[str], bytes]
WebUploader = Callable[[str, bytes, str], dict[str, Any]]
VersionWaiter = Callable[[str, str, int], dict[str, Any]]


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


def _fetch_latest_release() -> dict[str, Any]:
    req = urlrequest.Request(
        LATEST_RELEASE_URL,
        method='GET',
        headers={'Accept': 'application/vnd.github+json'},
    )
    with urlrequest.urlopen(req, timeout=10) as resp:
        parsed = json.load(resp)
    if not isinstance(parsed, dict):
        raise RuntimeError('Latest release payload is invalid.')

    version = _clean_version(parsed.get('tag_name'))
    assets = parsed.get('assets', [])
    asset_map: dict[str, str] = {}
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get('name', '') or '')
            url = str(asset.get('browser_download_url', '') or '').strip()
            if not url:
                continue
            if name.startswith('ulanzi_TC001_') and name.endswith('.bin'):
                asset_map['ulanzi'] = url
            elif name.startswith('old_awtrix2_conversion_') and name.endswith('.bin'):
                asset_map['awtrix2'] = url

    return {
        'version': version,
        'asset_url': asset_map.get('ulanzi', ''),
        'ulanzi_asset_url': asset_map.get('ulanzi', ''),
        'awtrix2_asset_url': asset_map.get('awtrix2', ''),
    }


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


def _download_firmware(url: str) -> bytes:
    req = urlrequest.Request(url, method='GET')
    with urlrequest.urlopen(req, timeout=60) as resp:
        return resp.read()


def _upload_firmware_via_web(ip: str, payload: bytes, filename: str) -> dict[str, Any]:
    boundary = f'----awtrix-{int(time.time() * 1000)}'
    parts = [
        f'--{boundary}\r\n'.encode('utf-8'),
        f'Content-Disposition: form-data; name="firmware"; filename="{filename}"\r\n'.encode('utf-8'),
        b'Content-Type: application/octet-stream\r\n\r\n',
        payload,
        f'\r\n--{boundary}--\r\n'.encode('utf-8'),
    ]
    body = b''.join(parts)
    req = urlrequest.Request(
        f'http://{ip}/update',
        data=body,
        method='POST',
        headers={
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(len(body)),
        },
    )
    with urlrequest.urlopen(req, timeout=180) as resp:
        return {
            'ip': ip,
            'status_code': int(getattr(resp, 'status', 200) or 200),
            'body': resp.read().decode('utf-8', 'replace').strip(),
            'ok': True,
        }


class DisplayUpdateService:
    def __init__(
        self,
        *,
        latest_version_fetcher: LatestVersionFetcher | None = None,
        release_fetcher: ReleaseFetcher | None = None,
        stats_fetcher: StatsFetcher | None = None,
        update_trigger: UpdateTrigger | None = None,
        firmware_downloader: FirmwareDownloader | None = None,
        web_uploader: WebUploader | None = None,
        version_waiter: VersionWaiter | None = None,
        cache_ttl_s: int = 900,
    ) -> None:
        self.latest_version_fetcher = latest_version_fetcher or _fetch_latest_version
        self.release_fetcher = release_fetcher if release_fetcher is not None else (
            None if latest_version_fetcher is not None else _fetch_latest_release
        )
        self.stats_fetcher = stats_fetcher or _fetch_display_stats
        self.update_trigger = update_trigger or _trigger_display_update
        self.firmware_downloader = firmware_downloader or _download_firmware
        self.web_uploader = web_uploader or _upload_firmware_via_web
        self.cache_ttl_s = max(30, int(cache_ttl_s or 900))
        self._lock = threading.Lock()
        self._latest_cache = {
            'version': '',
            'asset_url': '',
            'ulanzi_asset_url': '',
            'awtrix2_asset_url': '',
            'checked_at_ms': 0,
            'error': '',
        }
        self.version_waiter = version_waiter or self._wait_for_version

    def latest_version(self, refresh: bool = False) -> dict[str, Any]:
        now_ms = int(time.time() * 1000)
        with self._lock:
            cached = dict(self._latest_cache)
        if not refresh and cached['version'] and (now_ms - int(cached['checked_at_ms'] or 0)) < (self.cache_ttl_s * 1000):
            return cached

        version = ''
        asset_url = ''
        ulangan_asset_url = ''
        awtrix2_asset_url = ''
        error = ''
        try:
            release_data = self.release_fetcher() if self.release_fetcher is not None else {}
            if isinstance(release_data, dict):
                version = _clean_version(release_data.get('version'))
                asset_url = _clean_version(release_data.get('asset_url'))
                ulangan_asset_url = _clean_version(release_data.get('ulanzi_asset_url'))
                awtrix2_asset_url = _clean_version(release_data.get('awtrix2_asset_url'))
            if not version:
                version = _clean_version(self.latest_version_fetcher())
            if not version:
                raise RuntimeError('Latest AWTRIX version is empty.')
        except Exception as exc:
            error = str(exc)
            version = _clean_version(cached.get('version'))
            asset_url = _clean_version(cached.get('asset_url'))
            ulangan_asset_url = _clean_version(cached.get('ulanzi_asset_url'))
            awtrix2_asset_url = _clean_version(cached.get('awtrix2_asset_url'))

        payload = {
            'version': version,
            'asset_url': asset_url,
            'ulanzi_asset_url': ulangan_asset_url,
            'awtrix2_asset_url': awtrix2_asset_url,
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

    @staticmethod
    def _select_asset_url(latest: dict[str, Any], stats: dict[str, Any]) -> str:
        device_type = stats.get('type')
        if device_type == 0:
            return _clean_version(latest.get('ulanzi_asset_url') or latest.get('asset_url'))
        return _clean_version(latest.get('awtrix2_asset_url') or latest.get('asset_url'))

    def _wait_for_version(self, ip: str, target_version: str, timeout_s: int = 120) -> dict[str, Any]:
        deadline = time.time() + max(10, int(timeout_s or 120))
        last_error = ''
        while time.time() < deadline:
            try:
                stats = self.stats_fetcher(ip)
            except Exception as exc:
                last_error = str(exc)
                time.sleep(5)
                continue
            if _clean_version(stats.get('version')) == _clean_version(target_version):
                return stats
            time.sleep(5)
        raise TimeoutError(f'Version {target_version} wurde nicht bestaetigt. {last_error}'.strip())

    def trigger_update(self, ip: str) -> dict[str, Any]:
        clean_ip = str(ip or '').strip()
        if not clean_ip:
            raise ValueError('ip is required')

        current = self.status(clean_ip, refresh=True)
        current_version = _clean_version(current.get('current_version'))
        target_version = _clean_version(current.get('latest_version'))
        if current_version and target_version and not _is_newer_version(target_version, current_version):
            return {
                'ip': clean_ip,
                'status_code': 200,
                'body': 'Bereits aktuell.',
                'ok': True,
                'mode': 'noop',
                'current_version': current_version,
                'target_version': target_version,
                'final_version': current_version,
            }

        native_result = self.update_trigger(clean_ip)
        native_body = _clean_version(native_result.get('body'))
        native_status = int(native_result.get('status_code', 0) or 0)

        if native_result.get('ok') and target_version:
            try:
                confirmed = self.version_waiter(clean_ip, target_version, 120)
                final_version = _clean_version(confirmed.get('version'))
                return {
                    'ip': clean_ip,
                    'status_code': native_status or 200,
                    'body': f'Update erfolgreich auf {final_version}.',
                    'ok': final_version == target_version,
                    'mode': 'device-ota',
                    'current_version': current_version,
                    'target_version': target_version,
                    'final_version': final_version,
                }
            except Exception as exc:
                return {
                    'ip': clean_ip,
                    'status_code': 502,
                    'body': f'OTA gestartet, neue Version aber nicht bestaetigt: {exc}',
                    'ok': False,
                    'mode': 'device-ota',
                    'current_version': current_version,
                    'target_version': target_version,
                    'final_version': current_version,
                }

        if native_status == 404 and native_body == 'NoUpdateFound' and current_version and target_version:
            latest = self.latest_version(refresh=True)
            stats = self.stats_fetcher(clean_ip)
            asset_url = self._select_asset_url(latest, stats)
            if not asset_url:
                return {
                    'ip': clean_ip,
                    'status_code': 502,
                    'body': 'Kein passendes Firmware-Asset gefunden.',
                    'ok': False,
                    'mode': 'web-upload',
                    'current_version': current_version,
                    'target_version': target_version,
                    'final_version': current_version,
                }
            filename = asset_url.rsplit('/', 1)[-1] or 'firmware.bin'
            try:
                firmware = self.firmware_downloader(asset_url)
                upload_result = self.web_uploader(clean_ip, firmware, filename)
                confirmed = self.version_waiter(clean_ip, target_version, 120)
                final_version = _clean_version(confirmed.get('version'))
                return {
                    'ip': clean_ip,
                    'status_code': int(upload_result.get('status_code', 200) or 200),
                    'body': f'Update erfolgreich auf {final_version}.',
                    'ok': final_version == target_version,
                    'mode': 'web-upload',
                    'current_version': current_version,
                    'target_version': target_version,
                    'final_version': final_version,
                }
            except Exception as exc:
                return {
                    'ip': clean_ip,
                    'status_code': 502,
                    'body': f'Firmware-Upload fehlgeschlagen: {exc}',
                    'ok': False,
                    'mode': 'web-upload',
                    'current_version': current_version,
                    'target_version': target_version,
                    'final_version': current_version,
                }

        return {
            'ip': clean_ip,
            'status_code': native_status or 500,
            'body': native_body or 'Update fehlgeschlagen.',
            'ok': bool(native_result.get('ok', False)),
            'mode': 'device-ota',
            'current_version': current_version,
            'target_version': target_version,
            'final_version': current_version,
        }
