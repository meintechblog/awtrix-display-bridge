import tempfile
import unittest

from bridge.config_store import ConfigStore


class ConfigStoreTests(unittest.TestCase):
    def test_load_returns_default_shape_when_file_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ConfigStore(f'{tmpdir}/app-config.json')
            payload = store.load()

        self.assertEqual(payload['version'], 1)
        self.assertEqual(payload['displays'], [])
        self.assertEqual(payload['inputs'], [])
        self.assertEqual(payload['bindings'], [])

    def test_replace_config_persists_displays_inputs_and_bindings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ConfigStore(f'{tmpdir}/app-config.json')
            store.replace_config(
                displays=[{'id': 'd-1', 'name': 'Main', 'ip': '192.168.3.126'}],
                inputs=[{'id': 'i-1', 'kind': 'text', 'name': 'Status'}],
                bindings=[{'id': 'b-1', 'display_ids': ['d-1'], 'input_id': 'i-1'}],
            )

            loaded = store.load()

        self.assertEqual(loaded['displays'][0]['id'], 'd-1')
        self.assertEqual(loaded['inputs'][0]['kind'], 'text')
        self.assertEqual(loaded['bindings'][0]['input_id'], 'i-1')

    def test_load_strips_legacy_mqtt_stale_guard_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = f'{tmpdir}/app-config.json'
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(
                    '{"version":1,"updated_at":1,"displays":[],"inputs":[{"id":"mqtt-1","kind":"mqtt","name":"MQTT","maxStaleMs":"2500"}],"bindings":[]}'
                )

            store = ConfigStore(path)
            loaded = store.load()

        self.assertEqual(loaded['inputs'][0]['kind'], 'mqtt')
        self.assertNotIn('maxStaleMs', loaded['inputs'][0])


if __name__ == '__main__':
    unittest.main()
