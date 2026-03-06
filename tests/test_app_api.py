from __future__ import annotations

import json
import tempfile
import unittest
from urllib import request

from bridge.mqtt_bridge import build_server


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
            server, thread = build_server('127.0.0.1', 0, app_config_path=f'{tmpdir}/app-config.json')
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
            server, thread = build_server('127.0.0.1', 0, app_config_path=f'{tmpdir}/app-config.json')
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


if __name__ == '__main__':
    unittest.main()
