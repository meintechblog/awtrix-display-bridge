#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class SpaRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, directory: str, **kwargs: Any) -> None:
        self._directory = directory
        super().__init__(*args, directory=directory, **kwargs)

    def send_head(self):  # type: ignore[override]
        parsed = urlparse(self.path)
        path = parsed.path or '/'
        local_path = Path(self.translate_path(path))

        if local_path.exists():
            return super().send_head()

        suffix = Path(path).suffix
        if suffix or path.startswith('/api/'):
            self.send_error(404, 'Not found')
            return None

        index_path = Path(self._directory) / 'index.html'
        if not index_path.exists():
            self.send_error(404, 'index.html not found')
            return None

        self.path = '/index.html'
        return super().send_head()

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def build_server(
    host: str,
    port: int,
    *,
    root: str,
    start_thread: bool = True,
) -> tuple[ThreadingHTTPServer, threading.Thread | None]:
    directory = os.path.abspath(root)

    def handler(*args: Any, **kwargs: Any) -> SpaRequestHandler:
        return SpaRequestHandler(*args, directory=directory, **kwargs)

    server = ThreadingHTTPServer((host, port), handler)
    thread = None
    if start_thread:
        thread = threading.Thread(target=server.serve_forever, name='awtrix-webapp-http', daemon=True)
        thread.start()
    return server, thread


def main() -> None:
    parser = argparse.ArgumentParser(description='SPA-capable static server for the AWTRIX webapp')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=80)
    parser.add_argument('--root', default='/var/www/ulanzi')
    args = parser.parse_args()

    server, _ = build_server(args.host, args.port, root=args.root, start_thread=False)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
