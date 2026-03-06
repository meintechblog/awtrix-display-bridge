from __future__ import annotations

import unittest

from bridge.display_discovery import DisplayDiscoveryService


class DisplayDiscoveryTests(unittest.TestCase):
    def test_scan_filters_configured_ips_and_normalizes_awtrix_candidates(self):
        service = DisplayDiscoveryService(
            interval_s=30,
            interface_provider=lambda: ['192.168.3.0/30'],
            probe=lambda ip: {
                'ip': ip,
                'name': 'AWTRIX',
                'version': '0.97',
                'app': 'Time',
                'wifi_signal': -62,
                'matrix': True,
            } if ip == '192.168.3.2' else None,
        )

        results = service.run_scan(excluded_ips={'192.168.3.1'})

        self.assertEqual(results['count'], 1)
        self.assertEqual(results['items'][0]['ip'], '192.168.3.2')
        self.assertEqual(results['items'][0]['name'], 'AWTRIX')
        self.assertEqual(results['items'][0]['version'], '0.97')

    def test_snapshot_uses_background_cache(self):
        service = DisplayDiscoveryService(
            interval_s=30,
            interface_provider=lambda: [],
            probe=lambda ip: None,
        )

        service._update_cache(
            {
                'items': [{'ip': '192.168.3.50', 'name': 'Desk'}],
                'count': 1,
                'error': '',
                'updated_at_ms': 1772870400000,
                'scan_active': False,
            }
        )

        snapshot = service.snapshot(excluded_ips=set())

        self.assertEqual(snapshot['count'], 1)
        self.assertEqual(snapshot['items'][0]['ip'], '192.168.3.50')


if __name__ == '__main__':
    unittest.main()
