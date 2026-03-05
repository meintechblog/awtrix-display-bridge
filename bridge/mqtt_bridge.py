#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import paho.mqtt.client as mqtt

LOG = logging.getLogger('mqtt-bridge')


def _decode_payload(data: bytes, limit: int = 2000) -> str:
    try:
        text = data.decode('utf-8', 'replace')
    except Exception:
        text = repr(data)
    if len(text) > limit:
        return text[: limit - 1] + '...'
    return text


def _extract_json_keys(payload: str, limit: int = 25) -> list[str]:
    try:
        parsed = json.loads(payload)
    except Exception:
        return []
    if not isinstance(parsed, dict):
        return []
    keys = [str(k) for k in parsed.keys()]
    keys.sort()
    return keys[:limit]


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


class LiveSession:
    def __init__(self, broker_host: str, broker_port: int) -> None:
        self.broker_host = broker_host
        self.broker_port = broker_port
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._values: dict[str, dict[str, Any]] = {}
        self._msg_count = 0
        self._last_msg_at = 0
        self._last_error = ''
        self._connected = False
        self._started_at = int(time.time())

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        with self._cond:
            self._connected = True
            self._last_error = ''
            self._cond.notify_all()
        client.subscribe('#', qos=0)

    def _on_disconnect(self, client, userdata, reason_code, properties=None):
        with self._cond:
            self._connected = False
            self._last_error = f'disconnected: {reason_code}'
            self._cond.notify_all()

    def _on_message(self, client, userdata, msg):
        topic = str(msg.topic or '').strip()
        if not topic:
            return

        payload = _decode_payload(msg.payload)
        now = int(time.time())
        keys = _extract_json_keys(payload)

        with self._cond:
            self._msg_count += 1
            self._last_msg_at = now
            self._values[topic] = {
                'topic': topic,
                'payload': payload,
                'json_keys': keys,
                'updated_at': now,
                'message_no': self._msg_count,
            }
            self._cond.notify_all()

    def start(self) -> None:
        self._client.connect(self.broker_host, self.broker_port, keepalive=30)
        self._client.loop_start()

    def stop(self) -> None:
        try:
            self._client.loop_stop()
        except Exception:
            pass
        try:
            self._client.disconnect()
        except Exception:
            pass

    def get_topic(self, topic: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._values.get(topic)
            if item is None:
                return None
            return dict(item)

    def wait_for_topic(self, topic: str, timeout_s: float, min_message_no: int = 0) -> dict[str, Any] | None:
        timeout = max(0.2, min(float(timeout_s), 30.0))
        deadline = time.time() + timeout

        with self._cond:
            while True:
                item = self._values.get(topic)
                if item is not None and int(item.get('message_no', 0)) > int(min_message_no):
                    return dict(item)

                remaining = deadline - time.time()
                if remaining <= 0:
                    return None
                self._cond.wait(timeout=remaining)

    def snapshot(self, query: str = '', limit: int = 200) -> dict[str, Any]:
        q = query.strip().lower()
        lim = max(1, min(int(limit), 2000))

        with self._lock:
            topics = list(self._values.values())
            connected = self._connected
            msg_count = self._msg_count
            last_msg_at = self._last_msg_at
            last_error = self._last_error
            started_at = self._started_at

        if q:
            def matches(item: dict[str, Any]) -> bool:
                topic = str(item.get('topic', '')).lower()
                payload = str(item.get('payload', '')).lower()
                keys = ' '.join(str(k).lower() for k in (item.get('json_keys') or []))
                return q in topic or q in payload or q in keys

            filtered = [item for item in topics if matches(item)]
        else:
            filtered = topics

        filtered.sort(key=lambda x: int(x.get('updated_at', 0)), reverse=True)

        return {
            'broker': self.broker_host,
            'port': self.broker_port,
            'connected': connected,
            'started_at': started_at,
            'last_msg_at': last_msg_at,
            'message_count': msg_count,
            'count_total': len(topics),
            'count_filtered': len(filtered),
            'last_error': last_error,
            'topics': filtered[:lim],
        }


class MQTTBridge:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._topic_cache: dict[str, dict[str, Any]] = {}
        self._live_sessions: dict[str, LiveSession] = {}

    @staticmethod
    def _key(broker_host: str, broker_port: int) -> str:
        return f'{broker_host}:{broker_port}'

    def sync_topics(
        self,
        broker_host: str,
        broker_port: int = 1883,
        timeout_s: float = 3.0,
        max_topics: int = 1200,
    ) -> dict[str, Any]:
        topics: dict[str, str] = {}
        cache_key = self._key(broker_host, broker_port)

        def on_connect(client, userdata, flags, reason_code, properties=None):
            client.subscribe('#', qos=0)

        def on_message(client, userdata, msg):
            if not msg.topic:
                return
            if len(topics) >= max_topics and msg.topic not in topics:
                return
            topics[msg.topic] = _decode_payload(msg.payload)

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = on_connect
        client.on_message = on_message

        started = time.time()
        try:
            client.connect(broker_host, broker_port, keepalive=10)
            client.loop_start()
            time.sleep(max(0.5, min(timeout_s, 25.0)))
        finally:
            try:
                client.loop_stop()
            except Exception:
                pass
            try:
                client.disconnect()
            except Exception:
                pass

        elapsed_ms = int((time.time() - started) * 1000)
        items = []
        for topic in sorted(topics.keys()):
            sample = topics[topic]
            keys = _extract_json_keys(sample)
            items.append(
                {
                    'topic': topic,
                    'sample': sample,
                    'json_keys': keys,
                }
            )

        snapshot = {
            'broker': broker_host,
            'port': broker_port,
            'synced_at': int(time.time()),
            'elapsed_ms': elapsed_ms,
            'count': len(items),
            'topics': items,
        }

        with self._lock:
            self._topic_cache[cache_key] = snapshot

        return snapshot

    def get_topic_value(
        self,
        broker_host: str,
        broker_port: int,
        topic: str,
        timeout_s: float = 4.0,
        fresh: bool = False,
    ) -> dict[str, Any]:
        clean_topic = topic.strip()
        if not clean_topic:
            raise ValueError('topic is required')

        started = time.time()
        self.start_live(broker_host, broker_port)

        key = self._key(broker_host, broker_port)
        with self._lock:
            session = self._live_sessions.get(key)

        if session is None:
            raise RuntimeError('live session unavailable')

        cached = session.get_topic(clean_topic)
        if cached is not None and not fresh:
            return {
                'topic': clean_topic,
                'payload': str(cached.get('payload', '')),
                'received_at': int(cached.get('updated_at', 0) or 0),
                'elapsed_ms': int((time.time() - started) * 1000),
                'source': 'cache',
                'message_no': int(cached.get('message_no', 0) or 0),
                'stale': False,
            }

        min_msg_no = int(cached.get('message_no', 0) or 0) if (fresh and cached is not None) else 0
        item = session.wait_for_topic(clean_topic, timeout_s=timeout_s, min_message_no=min_msg_no)
        if item is None:
            if cached is not None:
                return {
                    'topic': clean_topic,
                    'payload': str(cached.get('payload', '')),
                    'received_at': int(cached.get('updated_at', 0) or 0),
                    'elapsed_ms': int((time.time() - started) * 1000),
                    'source': 'cache-fallback',
                    'message_no': int(cached.get('message_no', 0) or 0),
                    'stale': True,
                }
            raise TimeoutError("No message received for topic '%s' within timeout" % clean_topic)

        return {
            'topic': clean_topic,
            'payload': str(item.get('payload', '')),
            'received_at': int(item.get('updated_at', 0) or 0),
            'elapsed_ms': int((time.time() - started) * 1000),
            'source': 'live',
            'message_no': int(item.get('message_no', 0) or 0),
            'stale': False,
        }

    def start_live(self, broker_host: str, broker_port: int) -> dict[str, Any]:
        key = self._key(broker_host, broker_port)
        with self._lock:
            existing = self._live_sessions.get(key)
            if existing is not None:
                return {
                    'broker': broker_host,
                    'port': broker_port,
                    'started': True,
                    'already_running': True,
                }

            session = LiveSession(broker_host, broker_port)
            self._live_sessions[key] = session

        try:
            session.start()
            return {
                'broker': broker_host,
                'port': broker_port,
                'started': True,
                'already_running': False,
            }
        except Exception:
            with self._lock:
                self._live_sessions.pop(key, None)
            raise

    def stop_live(self, broker_host: str, broker_port: int) -> dict[str, Any]:
        key = self._key(broker_host, broker_port)
        with self._lock:
            session = self._live_sessions.pop(key, None)

        if session is None:
            return {
                'broker': broker_host,
                'port': broker_port,
                'stopped': False,
                'was_running': False,
            }

        session.stop()
        return {
            'broker': broker_host,
            'port': broker_port,
            'stopped': True,
            'was_running': True,
        }

    def live_snapshot(
        self,
        broker_host: str,
        broker_port: int,
        query: str = '',
        limit: int = 200,
        auto_start: bool = True,
    ) -> dict[str, Any]:
        key = self._key(broker_host, broker_port)

        with self._lock:
            session = self._live_sessions.get(key)

        if session is None and auto_start:
            self.start_live(broker_host, broker_port)
            with self._lock:
                session = self._live_sessions.get(key)

        if session is None:
            return {
                'broker': broker_host,
                'port': broker_port,
                'connected': False,
                'count_total': 0,
                'count_filtered': 0,
                'topics': [],
                'message_count': 0,
                'last_msg_at': 0,
                'started_at': 0,
                'last_error': 'live session not running',
            }

        return session.snapshot(query=query, limit=limit)

    def shutdown(self) -> None:
        with self._lock:
            sessions = list(self._live_sessions.values())
            self._live_sessions.clear()

        for session in sessions:
            try:
                session.stop()
            except Exception:
                pass


class Handler(BaseHTTPRequestHandler):
    bridge = MQTTBridge()

    def _set_headers(self, code: int = 200) -> None:
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def _write_json(self, payload: dict[str, Any], code: int = 200) -> None:
        self._set_headers(code)
        self.wfile.write(json.dumps(payload, ensure_ascii=True).encode('utf-8'))

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get('Content-Length', '0'))
        raw = self.rfile.read(length) if length > 0 else b'{}'
        try:
            data = json.loads(raw.decode('utf-8'))
        except Exception as exc:
            raise ValueError(f'Invalid JSON: {exc}') from exc
        if not isinstance(data, dict):
            raise ValueError('JSON payload must be an object')
        return data

    def do_OPTIONS(self) -> None:
        self._set_headers(204)

    def do_GET(self) -> None:
        if self.path == '/health':
            self._write_json({'ok': True, 'service': 'mqtt-bridge'})
            return
        self._write_json({'ok': False, 'error': 'Not found'}, code=404)

    def do_POST(self) -> None:
        try:
            data = self._read_json()
            if self.path == '/mqtt/topics/sync':
                broker = str(data.get('broker_host', '')).strip()
                port = int(data.get('broker_port', 1883))
                timeout_s = float(data.get('timeout_s', 3))
                max_topics = int(data.get('max_topics', 1200))
                if not broker:
                    raise ValueError('broker_host is required')
                result = self.bridge.sync_topics(broker, port, timeout_s, max_topics)
                self._write_json({'ok': True, 'result': result})
                return

            if self.path == '/mqtt/topic/value':
                broker = str(data.get('broker_host', '')).strip()
                port = int(data.get('broker_port', 1883))
                topic = str(data.get('topic', '')).strip()
                timeout_s = float(data.get('timeout_s', 4))
                fresh = _to_bool(data.get('fresh', False), default=False)
                if not broker:
                    raise ValueError('broker_host is required')
                if not topic:
                    raise ValueError('topic is required')
                result = self.bridge.get_topic_value(broker, port, topic, timeout_s, fresh=fresh)
                self._write_json({'ok': True, 'result': result})
                return

            if self.path == '/mqtt/live/start':
                broker = str(data.get('broker_host', '')).strip()
                port = int(data.get('broker_port', 1883))
                if not broker:
                    raise ValueError('broker_host is required')
                result = self.bridge.start_live(broker, port)
                self._write_json({'ok': True, 'result': result})
                return

            if self.path == '/mqtt/live/stop':
                broker = str(data.get('broker_host', '')).strip()
                port = int(data.get('broker_port', 1883))
                if not broker:
                    raise ValueError('broker_host is required')
                result = self.bridge.stop_live(broker, port)
                self._write_json({'ok': True, 'result': result})
                return

            if self.path == '/mqtt/live/snapshot':
                broker = str(data.get('broker_host', '')).strip()
                port = int(data.get('broker_port', 1883))
                query = str(data.get('query', ''))
                limit = int(data.get('limit', 200))
                auto_start = _to_bool(data.get('auto_start', True), default=True)
                if not broker:
                    raise ValueError('broker_host is required')
                result = self.bridge.live_snapshot(broker, port, query=query, limit=limit, auto_start=auto_start)
                self._write_json({'ok': True, 'result': result})
                return

            self._write_json({'ok': False, 'error': 'Not found'}, code=404)
        except TimeoutError as exc:
            self._write_json({'ok': False, 'error': str(exc)}, code=504)
        except Exception as exc:
            LOG.exception('Request failed')
            self._write_json({'ok': False, 'error': str(exc)}, code=400)

    def log_message(self, fmt: str, *args: Any) -> None:
        LOG.info('%s - %s', self.client_address[0], fmt % args)


def main() -> None:
    parser = argparse.ArgumentParser(description='MQTT helper bridge for AWTRIX webapp')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8090)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    LOG.info('Starting MQTT bridge on %s:%s', args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            Handler.bridge.shutdown()
        except Exception:
            pass
        server.server_close()


if __name__ == '__main__':
    main()
