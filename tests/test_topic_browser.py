from __future__ import annotations

import unittest

from bridge.topic_browser import list_children


class TopicBrowserTests(unittest.TestCase):
    def test_lists_only_next_level_children(self):
        topics = [
            'trading-deluxxe/webapp/status/balance',
            'trading-deluxxe/webapp/status/equity',
            'trading-deluxxe/webapp/orders/today',
        ]

        items = list_children(topics, 'trading-deluxxe/webapp')

        self.assertEqual([item['segment'] for item in items], ['orders', 'status'])
        self.assertTrue(all(item['kind'] == 'branch' for item in items))

    def test_query_filters_children_by_segment_or_path(self):
        topics = [
            'trading-deluxxe/webapp/status/balance',
            'trading-deluxxe/webapp/status/equity',
            'trading-deluxxe/webapp/orders/today',
        ]

        items = list_children(topics, 'trading-deluxxe/webapp', query='stat')

        self.assertEqual([item['segment'] for item in items], ['status'])


if __name__ == '__main__':
    unittest.main()
