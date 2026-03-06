from __future__ import annotations

import time
import unittest

from bridge.display_updates import DisplayUpdateService


class DisplayUpdateTests(unittest.TestCase):
    def _wait_for_phase(self, service: DisplayUpdateService, job_id: str, expected_phase: str, timeout_s: float = 2.0) -> dict:
        deadline = time.time() + timeout_s
        snapshot = {}
        while time.time() < deadline:
            snapshot = service.job_status(job_id)
            if snapshot['phase'] == expected_phase:
                return snapshot
            time.sleep(0.01)
        self.fail(f'Job {job_id} did not reach phase {expected_phase}. Last snapshot: {snapshot}')

    def test_status_compares_current_version_with_cached_latest_version(self):
        latest_calls: list[str] = []
        stats_calls: list[str] = []
        service = DisplayUpdateService(
            latest_version_fetcher=lambda: latest_calls.append('latest') or '0.98',
            stats_fetcher=lambda ip: stats_calls.append(ip) or {'version': '0.96', 'app': 'Clock'},
            update_trigger=lambda ip: {'status_code': 200, 'body': 'OK'},
            cache_ttl_s=600,
        )

        first = service.status('192.168.3.126')
        second = service.status('192.168.3.126')

        self.assertEqual(first['ip'], '192.168.3.126')
        self.assertEqual(first['current_version'], '0.96')
        self.assertEqual(first['latest_version'], '0.98')
        self.assertTrue(first['update_available'])
        self.assertEqual(first['app'], 'Clock')
        self.assertEqual(second['latest_version'], '0.98')
        self.assertEqual(latest_calls, ['latest'])
        self.assertEqual(stats_calls, ['192.168.3.126', '192.168.3.126'])

    def test_trigger_update_falls_back_to_web_upload_when_native_ota_reports_no_update(self):
        download_calls: list[str] = []
        upload_calls: list[tuple[str, bytes, str]] = []
        wait_calls: list[tuple[str, str, int]] = []
        service = DisplayUpdateService(
            latest_version_fetcher=lambda: '0.98',
            release_fetcher=lambda: {'version': '0.98', 'asset_url': 'https://example.invalid/ulanzi_TC001_0.98.bin'},
            stats_fetcher=lambda ip: {'version': '0.96', 'app': 'Clock', 'type': 0},
            update_trigger=lambda ip: {'ip': ip, 'status_code': 404, 'body': 'NoUpdateFound', 'ok': False},
            firmware_downloader=lambda url: download_calls.append(url) or b'FW',
            web_uploader=lambda ip, payload, filename: upload_calls.append((ip, payload, filename)) or {
                'ip': ip,
                'status_code': 200,
                'body': 'Update Success! Rebooting...',
                'ok': True,
            },
            version_waiter=lambda ip, version, timeout_s=120: wait_calls.append((ip, version, timeout_s)) or {
                'version': '0.98',
                'app': 'Notification',
            },
        )

        result = service.trigger_update('192.168.3.126')

        self.assertTrue(result['ok'])
        self.assertEqual(result['mode'], 'web-upload')
        self.assertEqual(result['final_version'], '0.98')
        self.assertEqual(download_calls, ['https://example.invalid/ulanzi_TC001_0.98.bin'])
        self.assertEqual(upload_calls[0][0], '192.168.3.126')
        self.assertEqual(upload_calls[0][1], b'FW')
        self.assertEqual(upload_calls[0][2], 'ulanzi_TC001_0.98.bin')
        self.assertEqual(wait_calls, [('192.168.3.126', '0.98', 120)])

    def test_trigger_update_reports_already_current_without_native_ota_call(self):
        native_calls: list[str] = []
        service = DisplayUpdateService(
            latest_version_fetcher=lambda: '0.98',
            release_fetcher=lambda: {'version': '0.98', 'asset_url': 'https://example.invalid/ulanzi_TC001_0.98.bin'},
            stats_fetcher=lambda ip: {'version': '0.98', 'app': 'Clock', 'type': 0},
            update_trigger=lambda ip: native_calls.append(ip) or {'ip': ip, 'status_code': 200, 'body': 'OK', 'ok': True},
        )

        result = service.trigger_update('192.168.3.126')

        self.assertTrue(result['ok'])
        self.assertEqual(result['mode'], 'noop')
        self.assertEqual(result['body'], 'Bereits aktuell.')
        self.assertEqual(native_calls, [])

    def test_start_update_job_returns_job_id_and_completes_with_result(self):
        phase_gate = {'open': False}

        def stats_fetcher(ip: str) -> dict[str, str | int]:
            if not phase_gate['open']:
                return {'version': '0.96', 'app': 'Clock', 'type': 0}
            return {'version': '0.98', 'app': 'Notification', 'type': 0}

        service = DisplayUpdateService(
            latest_version_fetcher=lambda: '0.98',
            release_fetcher=lambda: {'version': '0.98', 'asset_url': 'https://example.invalid/fw.bin'},
            stats_fetcher=stats_fetcher,
            update_trigger=lambda ip: phase_gate.update(open=True) or {
                'ip': ip,
                'status_code': 200,
                'body': 'OK',
                'ok': True,
            },
        )

        started = service.start_update_job('192.168.3.126')

        self.assertEqual(started['ip'], '192.168.3.126')
        self.assertTrue(started['job_id'])
        self.assertIn(started['phase'], {'queued', 'checking', 'downloading', 'uploading', 'rebooting', 'verifying', 'completed'})

        completed = self._wait_for_phase(service, started['job_id'], 'completed')

        self.assertTrue(completed['done'])
        self.assertTrue(completed['ok'])
        self.assertEqual(completed['result']['final_version'], '0.98')
        self.assertEqual(completed['result']['mode'], 'device-ota')

    def test_start_update_job_records_failure_state(self):
        service = DisplayUpdateService(
            latest_version_fetcher=lambda: '0.98',
            release_fetcher=lambda: {'version': '0.98', 'asset_url': 'https://example.invalid/fw.bin'},
            stats_fetcher=lambda ip: {'version': '0.96', 'app': 'Clock', 'type': 0},
            update_trigger=lambda ip: {
                'ip': ip,
                'status_code': 500,
                'body': 'Boom',
                'ok': False,
            },
        )

        started = service.start_update_job('192.168.3.126')
        failed = self._wait_for_phase(service, started['job_id'], 'failed')

        self.assertTrue(failed['done'])
        self.assertFalse(failed['ok'])
        self.assertIn('Boom', failed['message'])
        self.assertEqual(failed['result']['body'], 'Boom')


if __name__ == '__main__':
    unittest.main()
