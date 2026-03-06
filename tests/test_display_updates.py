from __future__ import annotations

import unittest

from bridge.display_updates import DisplayUpdateService


class DisplayUpdateTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
