from __future__ import annotations

import unittest

from bridge.runtime_view import build_dashboard_summary, normalize_runtime_event


class RuntimeViewTests(unittest.TestCase):
    def test_build_dashboard_summary_counts_online_and_offline_displays(self):
        config = {
            'displays': [
                {'id': 'd-1', 'name': 'Main', 'ip': '192.168.3.126'},
                {'id': 'd-2', 'name': 'Side', 'ip': '192.168.3.127'},
            ],
            'inputs': [{'id': 'i-1'}, {'id': 'i-2'}],
            'bindings': [{'id': 'b-1'}],
        }
        runtime = {
            'display_status': {
                'd-1': {'state': 'online'},
                'd-2': {'state': 'offline'},
            },
            'live_brokers': 1,
        }

        summary = build_dashboard_summary(config, runtime)

        self.assertEqual(summary['totals']['displays'], 2)
        self.assertEqual(summary['totals']['online'], 1)
        self.assertEqual(summary['totals']['offline'], 1)
        self.assertEqual(summary['totals']['inputs'], 2)
        self.assertEqual(summary['totals']['bindings'], 1)
        self.assertEqual(summary['totals']['live_brokers'], 1)

    def test_normalize_runtime_event_shapes_payload_for_ui(self):
        event = normalize_runtime_event(
            event_type='mqtt.message',
            entity='topic',
            entity_id='trading-deluxxe/webapp/status/balance',
            state='updated',
            updated_at_ms=1772800000000,
            detail={'payload': '15568.91', 'message_no': 42},
        )

        self.assertEqual(event['type'], 'mqtt.message')
        self.assertEqual(event['entity'], 'topic')
        self.assertEqual(event['entity_id'], 'trading-deluxxe/webapp/status/balance')
        self.assertEqual(event['state'], 'updated')
        self.assertEqual(event['detail']['message_no'], 42)


if __name__ == '__main__':
    unittest.main()
