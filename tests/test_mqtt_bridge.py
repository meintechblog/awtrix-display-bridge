import unittest
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
    def _emit(self, session: LiveSession, topic: str, payload: str):
        msg = SimpleNamespace(topic=topic, payload=payload.encode('utf-8'))
        session._on_message(None, None, msg)

    def test_sync_topics_uses_existing_live_session(self):
        bridge = MQTTBridge()
        session = LiveSession('broker.local', 1883)
        bridge._live_sessions['broker.local:1883'] = session

        self._emit(session, 'trading/status/balance', '{"balance":123}')
        self._emit(session, 'trading/status/equity', '{"equity":456}')

        result = bridge.sync_topics('broker.local', 1883, timeout_s=0.1, max_topics=100)
        topics = [item['topic'] for item in result['topics']]
        self.assertIn('trading/status/balance', topics)
        self.assertIn('trading/status/equity', topics)
        self.assertEqual(result['source'], 'live-session')


if __name__ == '__main__':
    unittest.main()
