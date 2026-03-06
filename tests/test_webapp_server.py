from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from urllib import error, request

from bridge.webapp_server import build_server


class WebAppServerTests(unittest.TestCase):
    def test_deep_link_falls_back_to_index_html(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / 'index.html').write_text('<html><body>app-shell</body></html>', encoding='utf-8')
            server, thread = build_server('127.0.0.1', 0, root=str(root), start_thread=True)
            try:
                with request.urlopen(f'http://127.0.0.1:{server.server_address[1]}/displays', timeout=5) as resp:
                    body = resp.read().decode('utf-8')
                    status = getattr(resp, 'status', 200)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertEqual(status, 200)
        self.assertIn('app-shell', body)

    def test_missing_asset_with_extension_stays_404(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / 'index.html').write_text('<html><body>app-shell</body></html>', encoding='utf-8')
            server, thread = build_server('127.0.0.1', 0, root=str(root), start_thread=True)
            try:
                with self.assertRaises(error.HTTPError) as ctx:
                    request.urlopen(f'http://127.0.0.1:{server.server_address[1]}/assets/missing.js', timeout=5)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertEqual(ctx.exception.code, 404)


if __name__ == '__main__':
    unittest.main()
