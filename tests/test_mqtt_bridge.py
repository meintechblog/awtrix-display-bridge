import unittest
import os
import tempfile
from types import SimpleNamespace

from bridge.mqtt_bridge import LiveSession, MQTTBridge, _topic_matches_filter


class TopicMatchTests(unittest.TestCase):
    def test_topic_filter_hash(self):
        self.assertTrue(_topic_matches_filter('a/b/c', 'a/#'))
        self.assertFalse(_topic_matches_filter('a/b/c', 'a/b/#/x'))

    def test_topic_filter_plus(self):
        self.assertTrue(_topic_matches_filter('a/b/c', 'a/+/c'))
        self.assertFalse(_topic_matches_filter('a/b/c', 'a/+/d'))


class LiveSessionTests(unittest.TestCase):
    def setUp(self):
        self.session = LiveSession('127.0.0.1', 1883)

    def _emit(self, topic: str, payload: str):
        msg = SimpleNamespace(topic=topic, payload=payload.encode('utf-8'))
        self.session._on_message(None, None, msg)

    def test_subscriber_receives_matching_topic(self):
        sub_id = self.session.add_subscriber(topic_filters=['foo/#'])
        self._emit('foo/bar', '{"v":1}')
        event = self.session.pop_subscriber_event(sub_id, timeout_s=0.2)
        self.assertIsNotNone(event)
        self.assertEqual(event['topic'], 'foo/bar')

    def test_subscriber_replay_uses_last_message(self):
        self._emit('a/one', '1')
        self._emit('a/two', '2')
        sub_id = self.session.add_subscriber(topic_filters=['a/#'], last_message_no=1)
        event = self.session.pop_subscriber_event(sub_id, timeout_s=0.2)
        self.assertIsNotNone(event)
        self.assertEqual(event['topic'], 'a/two')

    def test_wait_for_topic_with_min_message(self):
        self._emit('x/y', 'old')
        old = self.session.get_topic('x/y')
        self.assertIsNotNone(old)
        item = self.session.wait_for_topic('x/y', timeout_s=0.2, min_message_no=old['message_no'])
        self.assertIsNone(item)
        self._emit('x/y', 'new')
        item2 = self.session.wait_for_topic('x/y', timeout_s=0.2, min_message_no=old['message_no'])
        self.assertIsNotNone(item2)
        self.assertEqual(item2['payload'], 'new')


class BridgeTests(unittest.TestCase):
    def make_bridge(self):
        tmpdir = tempfile.TemporaryDirectory()
        os.environ['AWTRIX_AUTO_ROUTES_FILE'] = os.path.join(tmpdir.name, 'auto-rules.json')
        bridge = MQTTBridge()
        return bridge, tmpdir

    def _emit(self, session: LiveSession, topic: str, payload: str):
        msg = SimpleNamespace(topic=topic, payload=payload.encode('utf-8'))
        session._on_message(None, None, msg)

    def test_sync_topics_uses_existing_live_session(self):
        bridge, tmpdir = self.make_bridge()
        try:
            session = LiveSession('broker.local', 1883)
            bridge._live_sessions['broker.local:1883'] = session

            self._emit(session, 'trading/status/balance', '{"balance":123}')
            self._emit(session, 'trading/status/equity', '{"equity":456}')

            result = bridge.sync_topics('broker.local', 1883, timeout_s=0.1, max_topics=100)
            topics = [item['topic'] for item in result['topics']]
            self.assertIn('trading/status/balance', topics)
            self.assertIn('trading/status/equity', topics)
            self.assertEqual(result['source'], 'live-session')
        finally:
            bridge.shutdown()
            tmpdir.cleanup()
            os.environ.pop('AWTRIX_AUTO_ROUTES_FILE', None)

    def test_auto_route_realtime_extracts_json_key(self):
        bridge, tmpdir = self.make_bridge()
        queued = []
        bridge._queue_auto_send = lambda rule, value, message_no: queued.append((rule['id'], value, message_no))
        bridge._ensure_live_for_auto_rules = lambda: None
        try:
            bridge.replace_auto_routes(
                display_ip='192.168.3.126',
                routes=[
                    {
                        'id': 'rule-1',
                        'title': 'Balance',
                        'broker_host': 'broker.local',
                        'broker_port': 1883,
                        'topic': 'status/main',
                        'json_key': 'balance',
                        'template': 'Balance: {value}',
                        'display_duration': '8',
                        'send_mode': 'realtime',
                    }
                ],
            )

            bridge._on_live_event(
                'broker.local',
                1883,
                {
                    'topic': 'status/main',
                    'payload': '{"balance":456.7}',
                    'updated_at_ms': 1772800000000,
                    'message_no': 21,
                },
            )

            self.assertEqual(len(queued), 1)
            self.assertEqual(queued[0][0], 'rule-1')
            self.assertEqual(queued[0][1], '456.7')
        finally:
            bridge.shutdown()
            tmpdir.cleanup()
            os.environ.pop('AWTRIX_AUTO_ROUTES_FILE', None)

    def test_auto_route_interval_stores_pending_value(self):
        bridge, tmpdir = self.make_bridge()
        queued = []
        bridge._queue_auto_send = lambda rule, value, message_no: queued.append((rule['id'], value, message_no))
        bridge._ensure_live_for_auto_rules = lambda: None
        try:
            bridge.replace_auto_routes(
                display_ip='192.168.3.126',
                routes=[
                    {
                        'id': 'rule-interval',
                        'title': 'Balance',
                        'broker_host': 'broker.local',
                        'broker_port': 1883,
                        'topic': 'status/main',
                        'json_key': '',
                        'template': '{value}',
                        'display_duration': '8',
                        'send_mode': '2',
                    }
                ],
            )

            bridge._on_live_event(
                'broker.local',
                1883,
                {
                    'topic': 'status/main',
                    'payload': '999',
                    'updated_at_ms': 1772800000000,
                    'message_no': 11,
                },
            )

            runtime = bridge._auto_runtime.get('rule-interval', {})
            self.assertEqual(runtime.get('pending_value'), '999')
            self.assertEqual(len(queued), 0)
        finally:
            bridge.shutdown()
            tmpdir.cleanup()
            os.environ.pop('AWTRIX_AUTO_ROUTES_FILE', None)

    def test_auto_route_realtime_does_not_drop_old_payloads(self):
        bridge, tmpdir = self.make_bridge()
        queued = []
        bridge._queue_auto_send = lambda rule, value, message_no: queued.append((rule['id'], value, message_no))
        bridge._ensure_live_for_auto_rules = lambda: None
        try:
            bridge.replace_auto_routes(
                display_ip='192.168.3.126',
                routes=[
                    {
                        'id': 'rule-old',
                        'title': 'Balance',
                        'broker_host': 'broker.local',
                        'broker_port': 1883,
                        'topic': 'status/main',
                        'json_key': 'balance',
                        'template': 'Balance: {value}',
                        'display_duration': '8',
                        'send_mode': 'realtime',
                    }
                ],
            )

            bridge._on_live_event(
                'broker.local',
                1883,
                {
                    'topic': 'status/main',
                    'payload': '{"timestamp_utc":"2020-01-01T00:00:00Z","balance":456.7}',
                    'updated_at_ms': 1772800000000,
                    'message_no': 21,
                },
            )

            self.assertEqual(len(queued), 1)
            self.assertEqual(queued[0][0], 'rule-old')
            self.assertEqual(queued[0][1], '456.7')
        finally:
            bridge.shutdown()
            tmpdir.cleanup()
            os.environ.pop('AWTRIX_AUTO_ROUTES_FILE', None)


if __name__ == '__main__':
    unittest.main()
