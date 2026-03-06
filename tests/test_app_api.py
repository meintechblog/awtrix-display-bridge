from __future__ import annotations

import json
import tempfile
import unittest
from types import SimpleNamespace
from urllib import request

from bridge.mqtt_bridge import LiveSession, build_server


class AppApiTests(unittest.TestCase):
    def _request_json(self, method: str, url: str, payload: dict | None = None) -> dict:
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        req = request.Request(url, data=body, method=method, headers=headers)
        with request.urlopen(req, timeout=5) as resp:
            return json.load(resp)

    def test_get_displays_returns_saved_display_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            server, thread = build_server('127.0.0.1', 0, app_config_path=f'{tmpdir}/app-config.json', start_discovery=False)
            try:
                server.bridge.config_store.replace_config(
                    displays=[{'id': 'd-1', 'name': 'Main', 'ip': '192.168.3.126'}],
                    inputs=[],
                    bindings=[],
                )
                payload = self._request_json(
                    'GET',
                    f'http://127.0.0.1:{server.server_address[1]}/api/displays',
                )
            finally:
                server.bridge.shutdown()
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertTrue(payload['ok'])
        self.assertEqual(payload['result']['items'][0]['name'], 'Main')

    def test_put_config_replaces_displays_inputs_and_bindings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            server, thread = build_server('127.0.0.1', 0, app_config_path=f'{tmpdir}/app-config.json', start_discovery=False)
            try:
                payload = self._request_json(
                    'PUT',
                    f'http://127.0.0.1:{server.server_address[1]}/api/config',
                    {
                        'displays': [{'id': 'd-1', 'name': 'Main', 'ip': '192.168.3.126'}],
                        'inputs': [{'id': 'i-1', 'kind': 'mqtt', 'name': 'Balance'}],
                        'bindings': [{'id': 'b-1', 'display_ids': ['d-1'], 'input_id': 'i-1'}],
                    },
                )
                stored = server.bridge.config_store.load()
            finally:
                server.bridge.shutdown()
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertTrue(payload['ok'])
        self.assertEqual(stored['inputs'][0]['name'], 'Balance')
        self.assertEqual(stored['bindings'][0]['input_id'], 'i-1')

    def test_get_dashboard_returns_summary_counts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            server, thread = build_server('127.0.0.1', 0, app_config_path=f'{tmpdir}/app-config.json', start_discovery=False)
            try:
                server.bridge.config_store.replace_config(
                    displays=[{'id': 'd-1', 'name': 'Main', 'ip': '192.168.3.126'}],
                    inputs=[{'id': 'i-1', 'kind': 'text', 'name': 'Banner'}],
                    bindings=[{'id': 'b-1', 'display_ids': ['d-1'], 'input_id': 'i-1'}],
                )
                payload = self._request_json(
                    'GET',
                    f'http://127.0.0.1:{server.server_address[1]}/api/dashboard',
                )
            finally:
                server.bridge.shutdown()
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertTrue(payload['ok'])
        self.assertEqual(payload['result']['totals']['displays'], 1)
        self.assertEqual(payload['result']['totals']['inputs'], 1)
        self.assertEqual(payload['result']['totals']['bindings'], 1)

    def test_get_topic_browser_returns_next_level_children(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            server, thread = build_server('127.0.0.1', 0, app_config_path=f'{tmpdir}/app-config.json', start_discovery=False)
            try:
                server.bridge._topic_cache['broker.local:1883'] = {
                    'topics': [
                        {'topic': 'trading-deluxxe/webapp/status/balance'},
                        {'topic': 'trading-deluxxe/webapp/status/equity'},
                        {'topic': 'trading-deluxxe/webapp/orders/today'},
                    ]
                }
                payload = self._request_json(
                    'GET',
                    (
                        f'http://127.0.0.1:{server.server_address[1]}/api/topics/browser'
                        '?broker_host=broker.local&broker_port=1883&prefix=trading-deluxxe/webapp'
                    ),
                )
            finally:
                server.bridge.shutdown()
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertTrue(payload['ok'])
        self.assertEqual([item['segment'] for item in payload['result']['items']], ['orders', 'status'])

    def test_get_topic_value_returns_cached_live_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            server, thread = build_server('127.0.0.1', 0, app_config_path=f'{tmpdir}/app-config.json', start_discovery=False)
            try:
                session = LiveSession('broker.local', 1883)
                session._on_message(
                    None,
                    None,
                    SimpleNamespace(
                        topic='trading-deluxxe/webapp/status/balance',
                        payload=b'15568.91',
                    ),
                )
                server.bridge._live_sessions['broker.local:1883'] = session
                payload = self._request_json(
                    'GET',
                    (
                        f'http://127.0.0.1:{server.server_address[1]}/api/topics/value'
                        '?broker_host=broker.local&broker_port=1883&topic=trading-deluxxe/webapp/status/balance'
                    ),
                )
            finally:
                server.bridge.shutdown()
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertTrue(payload['ok'])
        self.assertEqual(payload['result']['payload'], '15568.91')

    def test_get_discovery_displays_returns_cached_unconfigured_candidates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            server, thread = build_server('127.0.0.1', 0, app_config_path=f'{tmpdir}/app-config.json', start_discovery=False)
            try:
                server.bridge.config_store.replace_config(
                    displays=[{'id': 'd-1', 'name': 'Main', 'ip': '192.168.3.126'}],
                    inputs=[],
                    bindings=[],
                )
                server.bridge.display_discovery._update_cache(
                    {
                        'items': [
                            {'ip': '192.168.3.126', 'name': 'Main'},
                            {'ip': '192.168.3.150', 'name': 'Desk'},
                        ],
                        'count': 2,
                        'error': '',
                        'updated_at_ms': 1772870400000,
                        'scan_active': False,
                    }
                )
                payload = self._request_json(
                    'GET',
                    f'http://127.0.0.1:{server.server_address[1]}/api/discovery/displays',
                )
            finally:
                server.bridge.shutdown()
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertTrue(payload['ok'])
        self.assertEqual(payload['result']['count'], 1)
        self.assertEqual(payload['result']['items'][0]['ip'], '192.168.3.150')


if __name__ == '__main__':
    unittest.main()
