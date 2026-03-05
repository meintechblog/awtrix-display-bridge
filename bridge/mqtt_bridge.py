#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

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


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(float(value), high))


def _topic_matches_filter(topic: str, topic_filter: str) -> bool:
    if not topic_filter:
        return False

    topic_levels = topic.split('/')
    filter_levels = topic_filter.split('/')

    i = 0
    while i < len(filter_levels):
        level = filter_levels[i]
        if level == '#':
            return i == len(filter_levels) - 1
        if i >= len(topic_levels):
            return False
        if level != '+' and level != topic_levels[i]:
            return False
        i += 1

    return i == len(topic_levels)


def _topic_matches_any(topic: str, topic_filters: tuple[str, ...]) -> bool:
    if not topic_filters:
        return True
    for topic_filter in topic_filters:
        if _topic_matches_filter(topic, topic_filter):
            return True
    return False


@dataclass
class LiveSubscriber:
    subscriber_id: str
    topic_filters: tuple[str, ...]
    events: queue.Queue

    def matches(self, topic: str) -> bool:
        return _topic_matches_any(topic, self.topic_filters)


class LiveSession:
    def __init__(self, broker_host: str, broker_port: int) -> None:
        self.broker_host = broker_host
        self.broker_port = broker_port
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._values: dict[str, dict[str, Any]] = {}
        self._recent_events: deque[dict[str, Any]] = deque(maxlen=12000)
        self._msg_count = 0
        self._last_msg_at_ms = 0
        self._last_error = ''
        self._connected = False
        self._started_at = int(time.time())
        self._subscribers: dict[str, LiveSubscriber] = {}
        self._next_subscriber_id = 1

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.reconnect_delay_set(min_delay=1, max_delay=8)

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

    @staticmethod
    def _push_subscriber_event(subscriber: LiveSubscriber, event: dict[str, Any]) -> None:
        try:
            subscriber.events.put_nowait(dict(event))
            return
        except queue.Full:
            pass

        try:
            subscriber.events.get_nowait()
        except Exception:
            return

        try:
            subscriber.events.put_nowait(dict(event))
        except Exception:
            pass

    def _on_message(self, client, userdata, msg):
        topic = str(msg.topic or '').strip()
        if not topic:
            return

        payload = _decode_payload(msg.payload)
        now_ms = int(time.time() * 1000)
        keys = _extract_json_keys(payload)

        with self._cond:
            self._msg_count += 1
            message_no = self._msg_count
            event = {
                'topic': topic,
                'payload': payload,
                'json_keys': keys,
                'updated_at': now_ms // 1000,
                'updated_at_ms': now_ms,
                'message_no': message_no,
            }
            self._last_msg_at_ms = now_ms
            self._values[topic] = dict(event)
            self._recent_events.append(dict(event))

            subscribers = list(self._subscribers.values())
            for subscriber in subscribers:
                if subscriber.matches(topic):
                    self._push_subscriber_event(subscriber, event)

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

    def message_count(self) -> int:
        with self._lock:
            return self._msg_count

    def get_topic(self, topic: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._values.get(topic)
            if item is None:
                return None
            return dict(item)

    def wait_for_topic(self, topic: str, timeout_s: float, min_message_no: int = 0) -> dict[str, Any] | None:
        timeout = _clamp(timeout_s, 0.2, 30.0)
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

    def add_subscriber(
        self,
        topic_filters: list[str] | tuple[str, ...] | None = None,
        last_message_no: int = 0,
        queue_size: int = 400,
    ) -> str:
        if topic_filters is None:
            normalized_filters: tuple[str, ...] = ()
        else:
            normalized_filters = tuple(
                item.strip() for item in topic_filters if isinstance(item, str) and item.strip()
            )

        qsize = max(50, min(int(queue_size), 5000))

        with self._cond:
            subscriber_id = str(self._next_subscriber_id)
            self._next_subscriber_id += 1
            subscriber = LiveSubscriber(
                subscriber_id=subscriber_id,
                topic_filters=normalized_filters,
                events=queue.Queue(maxsize=qsize),
            )
            self._subscribers[subscriber_id] = subscriber

            if int(last_message_no) > 0:
                for event in self._recent_events:
                    if int(event.get('message_no', 0)) <= int(last_message_no):
                        continue
                    if subscriber.matches(str(event.get('topic', ''))):
                        self._push_subscriber_event(subscriber, event)

            return subscriber_id

    def pop_subscriber_event(self, subscriber_id: str, timeout_s: float = 15.0) -> dict[str, Any] | None:
        with self._lock:
            subscriber = self._subscribers.get(subscriber_id)
        if subscriber is None:
            raise KeyError('subscriber not found')

        timeout = _clamp(timeout_s, 0.2, 60.0)
        try:
            event = subscriber.events.get(timeout=timeout)
        except queue.Empty:
            return None

        return dict(event)

    def remove_subscriber(self, subscriber_id: str) -> None:
        with self._cond:
            self._subscribers.pop(subscriber_id, None)

    def topic_items(self, limit: int = 2000, sort_by: str = 'topic') -> list[dict[str, Any]]:
        lim = max(1, min(int(limit), 200000))

        with self._lock:
            topics = [dict(item) for item in self._values.values()]

        if sort_by == 'updated_at':
            topics.sort(key=lambda x: int(x.get('updated_at_ms', 0)), reverse=True)
        else:
            topics.sort(key=lambda x: str(x.get('topic', '')))

        return topics[:lim]

    def snapshot(self, query: str = '', limit: int = 200) -> dict[str, Any]:
        q = query.strip().lower()
        lim = max(1, min(int(limit), 200000))

        with self._lock:
            topics = [dict(item) for item in self._values.values()]
            connected = self._connected
            msg_count = self._msg_count
            last_msg_at_ms = self._last_msg_at_ms
            last_error = self._last_error
            started_at = self._started_at
            subscriber_count = len(self._subscribers)

        if q:

            def matches(item: dict[str, Any]) -> bool:
                topic = str(item.get('topic', '')).lower()
                payload = str(item.get('payload', '')).lower()
                keys = ' '.join(str(k).lower() for k in (item.get('json_keys') or []))
                return q in topic or q in payload or q in keys

            filtered = [item for item in topics if matches(item)]
        else:
            filtered = topics

        filtered.sort(key=lambda x: int(x.get('updated_at_ms', 0)), reverse=True)

        return {
            'broker': self.broker_host,
            'port': self.broker_port,
            'connected': connected,
            'started_at': started_at,
            'last_msg_at': last_msg_at_ms // 1000 if last_msg_at_ms else 0,
            'last_msg_at_ms': last_msg_at_ms,
            'message_count': msg_count,
            'count_total': len(topics),
            'count_filtered': len(filtered),
            'subscriber_count': subscriber_count,
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

    def _get_session(self, broker_host: str, broker_port: int) -> LiveSession | None:
        key = self._key(broker_host, broker_port)
        with self._lock:
            return self._live_sessions.get(key)

    def sync_topics(
        self,
        broker_host: str,
        broker_port: int = 1883,
        timeout_s: float = 3.0,
        max_topics: int = 1200,
    ) -> dict[str, Any]:
        started = time.time()
        self.start_live(broker_host, broker_port)
        session = self._get_session(broker_host, broker_port)
        if session is None:
            raise RuntimeError('live session unavailable')

        wait_s = _clamp(timeout_s, 0.5, 30.0)
        baseline = session.message_count()
        deadline = time.time() + wait_s
        while time.time() < deadline:
            if session.message_count() > baseline:
                break
            time.sleep(0.08)

        items = []
        for event in session.topic_items(limit=max_topics, sort_by='topic'):
            items.append(
                {
                    'topic': str(event.get('topic', '')),
                    'sample': str(event.get('payload', '')),
                    'json_keys': [str(k) for k in (event.get('json_keys') or [])],
                }
            )

        elapsed_ms = int((time.time() - started) * 1000)
        snapshot = {
            'broker': broker_host,
            'port': broker_port,
            'synced_at': int(time.time()),
            'elapsed_ms': elapsed_ms,
            'count': len(items),
            'source': 'live-session',
            'topics': items,
        }

        cache_key = self._key(broker_host, broker_port)
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

        session = self._get_session(broker_host, broker_port)
        if session is None:
            raise RuntimeError('live session unavailable')

        cached = session.get_topic(clean_topic)
        if cached is not None and not fresh:
            received_ms = int(cached.get('updated_at_ms', 0) or 0)
            return {
                'topic': clean_topic,
                'payload': str(cached.get('payload', '')),
                'received_at': received_ms // 1000 if received_ms else int(cached.get('updated_at', 0) or 0),
                'received_at_ms': received_ms,
                'elapsed_ms': int((time.time() - started) * 1000),
                'source': 'cache',
                'message_no': int(cached.get('message_no', 0) or 0),
                'stale': False,
            }

        min_msg_no = int(cached.get('message_no', 0) or 0) if (fresh and cached is not None) else 0
        item = session.wait_for_topic(clean_topic, timeout_s=timeout_s, min_message_no=min_msg_no)
        if item is None:
            if cached is not None:
                received_ms = int(cached.get('updated_at_ms', 0) or 0)
                return {
                    'topic': clean_topic,
                    'payload': str(cached.get('payload', '')),
                    'received_at': received_ms // 1000 if received_ms else int(cached.get('updated_at', 0) or 0),
                    'received_at_ms': received_ms,
                    'elapsed_ms': int((time.time() - started) * 1000),
                    'source': 'cache-fallback',
                    'message_no': int(cached.get('message_no', 0) or 0),
                    'stale': True,
                }
            raise TimeoutError("No message received for topic '%s' within timeout" % clean_topic)

        received_ms = int(item.get('updated_at_ms', 0) or 0)
        return {
            'topic': clean_topic,
            'payload': str(item.get('payload', '')),
            'received_at': received_ms // 1000 if received_ms else int(item.get('updated_at', 0) or 0),
            'received_at_ms': received_ms,
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

    def create_live_subscriber(
        self,
        broker_host: str,
        broker_port: int,
        topic_filters: list[str] | tuple[str, ...] | None = None,
        last_message_no: int = 0,
        queue_size: int = 400,
    ) -> dict[str, Any]:
        self.start_live(broker_host, broker_port)
        session = self._get_session(broker_host, broker_port)
        if session is None:
            raise RuntimeError('live session unavailable')

        subscriber_id = session.add_subscriber(
            topic_filters=topic_filters,
            last_message_no=last_message_no,
            queue_size=queue_size,
        )
        return {
            'broker': broker_host,
            'port': broker_port,
            'subscriber_id': subscriber_id,
            'topic_filters': list(topic_filters or []),
        }

    def wait_live_event(
        self,
        broker_host: str,
        broker_port: int,
        subscriber_id: str,
        timeout_s: float = 15.0,
    ) -> dict[str, Any] | None:
        session = self._get_session(broker_host, broker_port)
        if session is None:
            raise RuntimeError('live session unavailable')
        return session.pop_subscriber_event(subscriber_id=subscriber_id, timeout_s=timeout_s)

    def remove_live_subscriber(self, broker_host: str, broker_port: int, subscriber_id: str) -> None:
        session = self._get_session(broker_host, broker_port)
        if session is None:
            return
        session.remove_subscriber(subscriber_id)

    def live_snapshot(
        self,
        broker_host: str,
        broker_port: int,
        query: str = '',
        limit: int = 200,
        auto_start: bool = True,
    ) -> dict[str, Any]:
        session = self._get_session(broker_host, broker_port)

        if session is None and auto_start:
            self.start_live(broker_host, broker_port)
            session = self._get_session(broker_host, broker_port)

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
                'last_msg_at_ms': 0,
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

    def _set_headers(
        self,
        code: int = 200,
        content_type: str = 'application/json; charset=utf-8',
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type,Last-Event-ID')
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
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

    def _parse_topics(self, params: dict[str, list[str]]) -> list[str]:
        raw_items: list[str] = []
        raw_items.extend(params.get('topic', []))
        raw_items.extend(params.get('topics', []))

        topics: list[str] = []
        for item in raw_items:
            for part in str(item).split(','):
                topic = part.strip()
                if topic:
                    topics.append(topic)

        dedup: list[str] = []
        seen: set[str] = set()
        for topic in topics:
            if topic in seen:
                continue
            seen.add(topic)
            dedup.append(topic)
        return dedup

    def _stream_mqtt_events(self, parsed) -> None:
        params = parse_qs(parsed.query or '', keep_blank_values=False)

        broker = str((params.get('broker_host') or [''])[0]).strip()
        port = int((params.get('broker_port') or ['1883'])[0])
        heartbeat_s = _clamp(float((params.get('heartbeat_s') or ['15'])[0]), 5.0, 60.0)
        queue_size = int((params.get('queue_size') or ['400'])[0])
        topics = self._parse_topics(params)

        if not broker:
            raise ValueError('broker_host is required')

        last_message_no = 0
        raw_last = (params.get('last_message_no') or [''])[0]
        if raw_last:
            last_message_no = int(raw_last)
        elif self.headers.get('Last-Event-ID'):
            try:
                last_message_no = int(str(self.headers.get('Last-Event-ID', '0')).strip() or '0')
            except Exception:
                last_message_no = 0

        subscriber = self.bridge.create_live_subscriber(
            broker_host=broker,
            broker_port=port,
            topic_filters=topics,
            last_message_no=last_message_no,
            queue_size=queue_size,
        )
        subscriber_id = str(subscriber.get('subscriber_id'))

        self._set_headers(
            200,
            content_type='text/event-stream; charset=utf-8',
            extra_headers={
                'Cache-Control': 'no-cache, no-transform',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',
            },
        )

        try:
            self.wfile.write(b': connected\n\n')
            self.wfile.flush()

            while True:
                event = self.bridge.wait_live_event(
                    broker_host=broker,
                    broker_port=port,
                    subscriber_id=subscriber_id,
                    timeout_s=heartbeat_s,
                )

                if event is None:
                    self.wfile.write(b': ping\n\n')
                    self.wfile.flush()
                    continue

                payload = {
                    'topic': str(event.get('topic', '')),
                    'payload': str(event.get('payload', '')),
                    'json_keys': [str(k) for k in (event.get('json_keys') or [])],
                    'updated_at': int(event.get('updated_at', 0) or 0),
                    'updated_at_ms': int(event.get('updated_at_ms', 0) or 0),
                    'message_no': int(event.get('message_no', 0) or 0),
                }
                event_id = payload['message_no']
                blob = (
                    f'id: {event_id}\n'
                    'event: mqtt\n'
                    f'data: {json.dumps(payload, ensure_ascii=True)}\n\n'
                )
                self.wfile.write(blob.encode('utf-8'))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.bridge.remove_live_subscriber(broker, port, subscriber_id)

    def do_OPTIONS(self) -> None:
        self._set_headers(204)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == '/health':
            self._write_json({'ok': True, 'service': 'mqtt-bridge'})
            return

        if parsed.path == '/mqtt/live/events':
            try:
                self._stream_mqtt_events(parsed)
            except ValueError as exc:
                self._write_json({'ok': False, 'error': str(exc)}, code=400)
            except Exception as exc:
                LOG.exception('SSE request failed')
                try:
                    self._write_json({'ok': False, 'error': str(exc)}, code=500)
                except Exception:
                    pass
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
