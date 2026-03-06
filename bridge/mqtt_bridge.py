#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import parse_qs, urlparse

import paho.mqtt.client as mqtt

from bridge.app_api import collection_payload, config_payload
from bridge.config_store import ConfigStore
from bridge.display_discovery import DisplayDiscoveryService
from bridge.display_updates import DisplayUpdateService
from bridge.runtime_view import build_dashboard_summary, normalize_runtime_event
from bridge.topic_browser import list_children

LOG = logging.getLogger('mqtt-bridge')
_MISSING = object()


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


def _path_value(obj: Any, path: str) -> Any:
    if not path:
        return obj
    current = obj
    for part in [item.strip() for item in path.split('.') if item.strip()]:
        if current is None:
            return _MISSING
        if isinstance(current, list) and part.isdigit():
            idx = int(part)
            if idx < 0 or idx >= len(current):
                return _MISSING
            current = current[idx]
            continue
        if isinstance(current, dict):
            if part not in current:
                return _MISSING
            current = current.get(part)
            continue
        return _MISSING
    return current


def _extract_payload_value(raw_payload: str, json_key: str) -> str:
    key = str(json_key or '').strip()
    if not key:
        return str(raw_payload or '')
    parsed = json.loads(str(raw_payload or ''))
    selected = _path_value(parsed, key)
    if selected is _MISSING:
        raise KeyError(f'json key not found: {key}')
    if isinstance(selected, (dict, list)):
        return json.dumps(selected, ensure_ascii=True)
    return str(selected)


def _display_mode_to_seconds(mode: str, fallback: int = 8) -> int | None:
    value = str(mode or '').strip().lower()
    if value == 'until-change':
        return None
    try:
        sec = int(float(value))
    except Exception:
        sec = int(fallback)
    return max(1, min(sec, 120))


def _format_template(template: str, value: str) -> str:
    t = str(template or '').strip() or '{value}'
    if '{value}' in t:
        return t.replace('{value}', value)
    return f'{t} {value}'.strip()


@dataclass
class LiveSubscriber:
    subscriber_id: str
    topic_filters: tuple[str, ...]
    events: queue.Queue

    def matches(self, topic: str) -> bool:
        return _topic_matches_any(topic, self.topic_filters)


class LiveSession:
    def __init__(
        self,
        broker_host: str,
        broker_port: int,
        event_callback: Any | None = None,
    ) -> None:
        self.broker_host = broker_host
        self.broker_port = broker_port
        self._event_callback = event_callback
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

        callback = self._event_callback
        callback_event: dict[str, Any] | None = None
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
            callback_event = dict(event)

            subscribers = list(self._subscribers.values())
            for subscriber in subscribers:
                if subscriber.matches(topic):
                    self._push_subscriber_event(subscriber, event)

            self._cond.notify_all()

        if callback is not None and callback_event is not None:
            try:
                callback(self.broker_host, self.broker_port, callback_event)
            except Exception:
                LOG.exception('Live event callback failed (%s:%s)', self.broker_host, self.broker_port)

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
    def __init__(
        self,
        app_config_path: str | None = None,
        auto_rules_path: str | None = None,
        *,
        start_discovery: bool = True,
    ) -> None:
        self._lock = threading.Lock()
        self._topic_cache: dict[str, dict[str, Any]] = {}
        self._live_sessions: dict[str, LiveSession] = {}
        self.config_store = ConfigStore(
            app_config_path or os.environ.get('AWTRIX_APP_CONFIG_FILE', '/opt/ulanzi-bridge/app_config.json')
        )
        self.display_discovery = DisplayDiscoveryService(interval_s=30)
        self.display_updates = DisplayUpdateService()
        self._auto_lock = threading.Lock()
        self._auto_rules: dict[str, dict[str, Any]] = {}
        self._auto_runtime: dict[str, dict[str, Any]] = {}
        self._auto_send_queue: queue.Queue = queue.Queue(maxsize=2000)
        self._auto_stop = threading.Event()
        self._auto_rules_path = auto_rules_path or os.environ.get(
            'AWTRIX_AUTO_ROUTES_FILE', '/opt/ulanzi-bridge/auto_routes.json'
        )
        self._auto_sender_thread = threading.Thread(target=self._auto_sender_loop, name='awtrix-auto-sender', daemon=True)
        self._auto_tick_thread = threading.Thread(target=self._auto_tick_loop, name='awtrix-auto-tick', daemon=True)
        self._load_auto_rules()
        self._auto_sender_thread.start()
        self._auto_tick_thread.start()
        if start_discovery:
            self.display_discovery.start()

    @staticmethod
    def _key(broker_host: str, broker_port: int) -> str:
        return f'{broker_host}:{broker_port}'

    def _get_session(self, broker_host: str, broker_port: int) -> LiveSession | None:
        key = self._key(broker_host, broker_port)
        with self._lock:
            return self._live_sessions.get(key)

    @staticmethod
    def _empty_runtime() -> dict[str, Any]:
        return {
            'last_message_no': 0,
            'last_sent_value': '',
            'last_sent_message_no': 0,
            'pending_value': None,
            'pending_message_no': 0,
            'next_due_ms': 0,
            'last_error': '',
            'last_sent_at_ms': 0,
        }

    @staticmethod
    def _auto_mode_interval_ms(mode: str) -> int | None:
        clean = str(mode or '').strip().lower()
        if clean == 'realtime':
            return 0
        if clean.isdigit():
            sec = int(clean)
            if 1 <= sec <= 10:
                return sec * 1000
        return None

    def _normalize_auto_rule(self, raw: dict[str, Any], default_display_ip: str) -> dict[str, Any]:
        rule_id = str(raw.get('id', '')).strip()
        if not rule_id:
            raise ValueError('auto rule id is required')

        broker_host = str(raw.get('broker_host', '')).strip()
        topic = str(raw.get('topic', '')).strip()
        auto_mode = str(raw.get('auto_mode', raw.get('send_mode', 'off'))).strip().lower()
        if auto_mode not in {'realtime', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10'}:
            auto_mode = 'off'

        if not broker_host:
            raise ValueError(f'auto rule broker_host is required ({rule_id})')
        if not topic:
            raise ValueError(f'auto rule topic is required ({rule_id})')
        if auto_mode == 'off':
            raise ValueError(f'auto rule auto_mode is off ({rule_id})')

        display_ip = str(raw.get('display_ip', default_display_ip)).strip()
        if not display_ip:
            raise ValueError(f'auto rule display_ip is required ({rule_id})')

        broker_port = int(raw.get('broker_port', 1883))

        display_mode = str(raw.get('display_mode', raw.get('display_duration', '8'))).strip() or '8'
        rule = {
            'id': rule_id,
            'title': str(raw.get('title', 'MQTT')).strip() or 'MQTT',
            'display_ip': display_ip,
            'broker_host': broker_host,
            'broker_port': broker_port,
            'topic': topic,
            'json_key': str(raw.get('json_key', '')).strip(),
            'template': str(raw.get('template', '{value}')),
            'display_mode': display_mode,
            'auto_mode': auto_mode,
            'display_duration': display_mode,
            'send_mode': auto_mode,
            'enabled': _to_bool(raw.get('enabled', True), default=True),
        }
        return rule

    def _active_auto_brokers(self) -> list[tuple[str, int]]:
        with self._auto_lock:
            items = {
                (str(rule.get('broker_host', '')), int(rule.get('broker_port', 1883)))
                for rule in self._auto_rules.values()
                if _to_bool(rule.get('enabled', True), default=True) and str(rule.get('auto_mode', 'off')) != 'off'
            }
        return sorted(items)

    def _ensure_live_for_auto_rules(self) -> None:
        for broker_host, broker_port in self._active_auto_brokers():
            if not broker_host:
                continue
            try:
                self.start_live(broker_host, broker_port)
            except Exception:
                LOG.exception('Failed to start live session for auto rule broker %s:%s', broker_host, broker_port)

    def _load_auto_rules(self) -> None:
        if not os.path.exists(self._auto_rules_path):
            return
        try:
            with open(self._auto_rules_path, 'r', encoding='utf-8') as fh:
                payload = json.load(fh)
        except Exception:
            LOG.exception('Failed to load auto rules from %s', self._auto_rules_path)
            return

        raw_rules = payload.get('rules') if isinstance(payload, dict) else []
        if not isinstance(raw_rules, list):
            return

        rules: dict[str, dict[str, Any]] = {}
        runtime: dict[str, dict[str, Any]] = {}
        for item in raw_rules:
            if not isinstance(item, dict):
                continue
            try:
                rule = self._normalize_auto_rule(item, default_display_ip=str(item.get('display_ip', '')).strip())
            except Exception:
                continue
            rid = str(rule['id'])
            rules[rid] = rule
            runtime[rid] = self._empty_runtime()

        with self._auto_lock:
            self._auto_rules = rules
            self._auto_runtime = runtime

        self._ensure_live_for_auto_rules()

    def _save_auto_rules(self) -> None:
        with self._auto_lock:
            payload = {
                'updated_at': int(time.time()),
                'rules': list(self._auto_rules.values()),
            }
        parent = os.path.dirname(self._auto_rules_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        temp_path = f'{self._auto_rules_path}.tmp'
        with open(temp_path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=True, separators=(',', ':'))
        os.replace(temp_path, self._auto_rules_path)

    def replace_auto_routes(self, display_ip: str, routes: list[dict[str, Any]]) -> dict[str, Any]:
        base_display_ip = str(display_ip or '').strip()
        if not base_display_ip:
            raise ValueError('display_ip is required')
        if not isinstance(routes, list):
            raise ValueError('routes must be a list')

        new_rules: dict[str, dict[str, Any]] = {}
        for item in routes:
            if not isinstance(item, dict):
                continue
            rule = self._normalize_auto_rule(item, default_display_ip=base_display_ip)
            new_rules[str(rule['id'])] = rule

        with self._auto_lock:
            old_runtime = self._auto_runtime
            self._auto_rules = new_rules
            self._auto_runtime = {
                rid: dict(old_runtime.get(rid, self._empty_runtime()))
                for rid in new_rules.keys()
            }

        self._save_auto_rules()
        self._ensure_live_for_auto_rules()
        return self.list_auto_routes()

    def list_auto_routes(self) -> dict[str, Any]:
        with self._auto_lock:
            routes = list(self._auto_rules.values())
            runtime = {rid: dict(state) for rid, state in self._auto_runtime.items()}

        return {
            'count': len(routes),
            'rules': routes,
            'runtime': runtime,
        }

    def _queue_auto_send(self, rule: dict[str, Any], value: str, message_no: int) -> None:
        job = {
            'rule_id': str(rule.get('id', '')),
            'value': str(value),
            'message_no': int(message_no or 0),
            'queued_at_ms': int(time.time() * 1000),
        }
        if not job['rule_id']:
            return
        try:
            self._auto_send_queue.put_nowait(job)
            return
        except queue.Full:
            pass
        try:
            self._auto_send_queue.get_nowait()
        except Exception:
            return
        try:
            self._auto_send_queue.put_nowait(job)
        except Exception:
            pass

    def _post_awtrix_notify(self, display_ip: str, text: str, display_mode: str) -> None:
        payload = {
            'text': text,
            'textCase': 2,
            'center': True,
            'stack': False,
            'wakeup': True,
        }
        duration = _display_mode_to_seconds(display_mode)
        if duration is None:
            payload['hold'] = True
        else:
            payload['duration'] = duration

        body = json.dumps(payload, ensure_ascii=True).encode('utf-8')
        req = urlrequest.Request(
            f'http://{display_ip}/api/notify',
            data=body,
            method='POST',
            headers={'Content-Type': 'application/json'},
        )
        with urlrequest.urlopen(req, timeout=5) as res:
            if int(getattr(res, 'status', 200)) >= 400:
                raise RuntimeError(f'AWTRIX notify failed: HTTP {res.status}')

    def _auto_sender_loop(self) -> None:
        while not self._auto_stop.is_set():
            try:
                job = self._auto_send_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            rule_id = str(job.get('rule_id', ''))
            if not rule_id:
                continue
            with self._auto_lock:
                rule = self._auto_rules.get(rule_id)
                runtime = self._auto_runtime.get(rule_id)
                if rule is None or runtime is None:
                    continue
                value = str(job.get('value', ''))
                message_no = int(job.get('message_no', 0) or 0)
                if value == str(runtime.get('last_sent_value', '')):
                    runtime['last_sent_message_no'] = max(int(runtime.get('last_sent_message_no', 0) or 0), message_no)
                    continue
                display_ip = str(rule.get('display_ip', '')).strip()
                display_mode = str(rule.get('display_mode', '8'))
                text = _format_template(str(rule.get('template', '{value}')), value)
            if not display_ip:
                continue

            try:
                self._post_awtrix_notify(display_ip=display_ip, text=text, display_mode=display_mode)
                with self._auto_lock:
                    current = self._auto_runtime.get(rule_id)
                    if current is not None:
                        current['last_sent_value'] = value
                        current['last_sent_message_no'] = max(int(current.get('last_sent_message_no', 0) or 0), message_no)
                        current['last_sent_at_ms'] = int(time.time() * 1000)
                        current['last_error'] = ''
            except Exception as exc:
                LOG.error('Auto route send failed (%s): %s', rule_id, exc)
                with self._auto_lock:
                    current = self._auto_runtime.get(rule_id)
                    if current is not None:
                        current['last_error'] = str(exc)

    def _auto_tick_loop(self) -> None:
        while not self._auto_stop.is_set():
            now_ms = int(time.time() * 1000)
            due_jobs: list[tuple[dict[str, Any], str, int]] = []
            with self._auto_lock:
                for rule_id, rule in self._auto_rules.items():
                    if not _to_bool(rule.get('enabled', True), default=True):
                        continue
                    interval = self._auto_mode_interval_ms(str(rule.get('auto_mode', 'off')))
                    if interval is None or interval <= 0:
                        continue
                    runtime = self._auto_runtime.setdefault(rule_id, self._empty_runtime())
                    pending_value = runtime.get('pending_value')
                    if pending_value is None:
                        continue
                    next_due_ms = int(runtime.get('next_due_ms', 0) or 0)
                    if next_due_ms <= 0:
                        runtime['next_due_ms'] = now_ms + interval
                        continue
                    if now_ms < next_due_ms:
                        continue
                    value = str(pending_value)
                    msg_no = int(runtime.get('pending_message_no', 0) or 0)
                    runtime['pending_value'] = None
                    runtime['pending_message_no'] = 0
                    runtime['next_due_ms'] = now_ms + interval
                    if value == str(runtime.get('last_sent_value', '')):
                        runtime['last_sent_message_no'] = max(int(runtime.get('last_sent_message_no', 0) or 0), msg_no)
                        continue
                    due_jobs.append((dict(rule), value, msg_no))

            for rule, value, msg_no in due_jobs:
                self._queue_auto_send(rule, value, msg_no)

            self._auto_stop.wait(0.2)

    def _apply_event_to_rule_locked(self, rule: dict[str, Any], runtime: dict[str, Any], event: dict[str, Any]) -> None:
        message_no = int(event.get('message_no', 0) or 0)
        last_seen = int(runtime.get('last_message_no', 0) or 0)
        if message_no > 0 and message_no <= last_seen:
            return
        if message_no > 0:
            runtime['last_message_no'] = message_no

        raw_payload = str(event.get('payload', ''))
        json_key = str(rule.get('json_key', '')).strip()
        try:
            value = _extract_payload_value(raw_payload, json_key)
        except Exception as exc:
            runtime['last_error'] = str(exc)
            return

        mode = str(rule.get('auto_mode', 'off')).strip().lower()
        if mode == 'realtime':
            if value == str(runtime.get('last_sent_value', '')):
                runtime['last_sent_message_no'] = max(int(runtime.get('last_sent_message_no', 0) or 0), message_no)
                return
            self._queue_auto_send(rule, value, message_no)
            return

        interval = self._auto_mode_interval_ms(mode)
        if interval and interval > 0:
            runtime['pending_value'] = value
            runtime['pending_message_no'] = message_no
            if int(runtime.get('next_due_ms', 0) or 0) <= 0:
                runtime['next_due_ms'] = int(time.time() * 1000) + interval

    def _on_live_event(self, broker_host: str, broker_port: int, event: dict[str, Any]) -> None:
        topic = str(event.get('topic', '')).strip()
        if not topic:
            return
        with self._auto_lock:
            for rule_id, rule in self._auto_rules.items():
                if not _to_bool(rule.get('enabled', True), default=True):
                    continue
                if str(rule.get('auto_mode', 'off')) == 'off':
                    continue
                if str(rule.get('broker_host', '')) != broker_host:
                    continue
                if int(rule.get('broker_port', 1883)) != int(broker_port):
                    continue
                if str(rule.get('topic', '')).strip() != topic:
                    continue
                runtime = self._auto_runtime.setdefault(rule_id, self._empty_runtime())
                self._apply_event_to_rule_locked(rule, runtime, event)

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

            session = LiveSession(
                broker_host,
                broker_port,
                event_callback=self._on_live_event,
            )
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

    def runtime_snapshot(self) -> dict[str, Any]:
        with self._lock:
            live_brokers = len(self._live_sessions)
        with self._auto_lock:
            auto_routes = len(self._auto_rules)

        return {
            'display_status': {},
            'live_brokers': live_brokers,
            'auto_routes': auto_routes,
            'updated_at_ms': int(time.time() * 1000),
        }

    def topic_browser(
        self,
        broker_host: str,
        broker_port: int,
        prefix: str = '',
        query: str = '',
    ) -> dict[str, Any]:
        session = self._get_session(broker_host, broker_port)
        if session is not None:
            topic_items = session.topic_items(limit=200000, sort_by='topic')
            topics = [str(item.get('topic', '')) for item in topic_items]
        else:
            cache_key = self._key(broker_host, broker_port)
            with self._lock:
                snapshot = dict(self._topic_cache.get(cache_key, {}))
            raw_items = snapshot.get('topics', []) if isinstance(snapshot, dict) else []
            topics = [str(item.get('topic', '')) for item in raw_items if isinstance(item, dict)]

        items = list_children(topics, prefix=prefix, query=query)
        return {
            'broker': broker_host,
            'port': broker_port,
            'prefix': str(prefix or '').strip().strip('/'),
            'query': str(query or '').strip(),
            'count': len(items),
            'items': items,
        }

    def discovered_displays(self, refresh: bool = False) -> dict[str, Any]:
        config = self.config_store.load()
        excluded_ips = {
            str(item.get('ip', '')).strip()
            for item in config.get('displays', [])
            if isinstance(item, dict) and str(item.get('ip', '')).strip()
        }
        if refresh:
            payload = self.display_discovery.run_scan(excluded_ips=excluded_ips)
            self.display_discovery._update_cache(payload)
            return payload
        return self.display_discovery.snapshot(excluded_ips=excluded_ips)

    def shutdown(self) -> None:
        self._auto_stop.set()
        try:
            self._auto_sender_thread.join(timeout=1.0)
        except Exception:
            pass
        try:
            self._auto_tick_thread.join(timeout=1.0)
        except Exception:
            pass

        try:
            self.display_discovery.stop()
        except Exception:
            pass

        with self._lock:
            sessions = list(self._live_sessions.values())
            self._live_sessions.clear()

        for session in sessions:
            try:
                session.stop()
            except Exception:
                pass


class Handler(BaseHTTPRequestHandler):
    def _bridge(self) -> MQTTBridge:
        bridge = getattr(self.server, 'bridge', None)
        if bridge is None:
            raise RuntimeError('bridge unavailable')
        return bridge

    def _set_headers(
        self,
        code: int = 200,
        content_type: str = 'application/json; charset=utf-8',
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,PUT,OPTIONS')
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

        bridge = self._bridge()
        subscriber = bridge.create_live_subscriber(
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
                event = bridge.wait_live_event(
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
            self._bridge().remove_live_subscriber(broker, port, subscriber_id)

    def _stream_runtime_events(self, parsed) -> None:
        params = parse_qs(parsed.query or '', keep_blank_values=False)

        broker = str((params.get('broker_host') or [''])[0]).strip()
        port = int((params.get('broker_port') or ['1883'])[0])
        heartbeat_s = _clamp(float((params.get('heartbeat_s') or ['15'])[0]), 5.0, 60.0)
        queue_size = int((params.get('queue_size') or ['400'])[0])
        topics = self._parse_topics(params)

        if not broker:
            raise ValueError('broker_host is required')

        bridge = self._bridge()
        subscriber = bridge.create_live_subscriber(
            broker_host=broker,
            broker_port=port,
            topic_filters=topics,
            last_message_no=0,
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
                event = bridge.wait_live_event(
                    broker_host=broker,
                    broker_port=port,
                    subscriber_id=subscriber_id,
                    timeout_s=heartbeat_s,
                )
                if event is None:
                    self.wfile.write(b': ping\n\n')
                    self.wfile.flush()
                    continue

                payload = normalize_runtime_event(
                    event_type='mqtt.message',
                    entity='topic',
                    entity_id=str(event.get('topic', '')),
                    state='updated',
                    updated_at_ms=int(event.get('updated_at_ms', 0) or 0),
                    detail={
                        'topic': str(event.get('topic', '')),
                        'payload': str(event.get('payload', '')),
                        'json_keys': [str(item) for item in (event.get('json_keys') or [])],
                        'message_no': int(event.get('message_no', 0) or 0),
                    },
                )
                blob = (
                    f"id: {payload['detail']['message_no']}\n"
                    'event: runtime\n'
                    f'data: {json.dumps(payload, ensure_ascii=True)}\n\n'
                )
                self.wfile.write(blob.encode('utf-8'))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            bridge.remove_live_subscriber(broker, port, subscriber_id)

    def do_OPTIONS(self) -> None:
        self._set_headers(204)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        bridge = self._bridge()

        if parsed.path == '/health':
            self._write_json({'ok': True, 'service': 'mqtt-bridge'})
            return

        if parsed.path == '/api/config':
            self._write_json({'ok': True, 'result': config_payload(bridge.config_store.load())})
            return

        if parsed.path == '/api/dashboard':
            summary = build_dashboard_summary(bridge.config_store.load(), bridge.runtime_snapshot())
            self._write_json({'ok': True, 'result': summary})
            return

        if parsed.path == '/api/displays':
            self._write_json({'ok': True, 'result': collection_payload(bridge.config_store.load(), 'displays')})
            return

        if parsed.path == '/api/discovery/displays':
            params = parse_qs(parsed.query or '', keep_blank_values=False)
            refresh = _to_bool((params.get('refresh') or ['false'])[0], default=False)
            self._write_json({'ok': True, 'result': bridge.discovered_displays(refresh=refresh)})
            return

        if parsed.path == '/api/display/update-status':
            params = parse_qs(parsed.query or '', keep_blank_values=False)
            ip = str((params.get('ip') or [''])[0]).strip()
            refresh = _to_bool((params.get('refresh') or ['false'])[0], default=False)
            if not ip:
                self._write_json({'ok': False, 'error': 'ip is required'}, code=400)
                return
            self._write_json({'ok': True, 'result': bridge.display_updates.status(ip, refresh=refresh)})
            return

        if parsed.path == '/api/display/update/job':
            params = parse_qs(parsed.query or '', keep_blank_values=False)
            job_id = str((params.get('id') or [''])[0]).strip()
            if not job_id:
                self._write_json({'ok': False, 'error': 'id is required'}, code=400)
                return
            try:
                result = bridge.display_updates.job_status(job_id)
            except KeyError as exc:
                self._write_json({'ok': False, 'error': str(exc)}, code=404)
                return
            self._write_json({'ok': True, 'result': result})
            return

        if parsed.path == '/api/inputs':
            self._write_json({'ok': True, 'result': collection_payload(bridge.config_store.load(), 'inputs')})
            return

        if parsed.path == '/api/bindings':
            self._write_json({'ok': True, 'result': collection_payload(bridge.config_store.load(), 'bindings')})
            return

        if parsed.path == '/api/topics/browser':
            params = parse_qs(parsed.query or '', keep_blank_values=False)
            broker = str((params.get('broker_host') or [''])[0]).strip()
            port = int((params.get('broker_port') or ['1883'])[0])
            prefix = str((params.get('prefix') or [''])[0])
            query = str((params.get('query') or [''])[0])
            if not broker:
                self._write_json({'ok': False, 'error': 'broker_host is required'}, code=400)
                return
            result = bridge.topic_browser(broker, port, prefix=prefix, query=query)
            self._write_json({'ok': True, 'result': result})
            return

        if parsed.path == '/api/topics/value':
            params = parse_qs(parsed.query or '', keep_blank_values=False)
            broker = str((params.get('broker_host') or [''])[0]).strip()
            port = int((params.get('broker_port') or ['1883'])[0])
            topic = str((params.get('topic') or [''])[0]).strip()
            fresh = _to_bool((params.get('fresh') or ['false'])[0], default=False)
            timeout_s = float((params.get('timeout_s') or ['4'])[0])
            if not broker:
                self._write_json({'ok': False, 'error': 'broker_host is required'}, code=400)
                return
            if not topic:
                self._write_json({'ok': False, 'error': 'topic is required'}, code=400)
                return
            result = bridge.get_topic_value(broker, port, topic, timeout_s, fresh=fresh)
            self._write_json({'ok': True, 'result': result})
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

        if parsed.path == '/api/runtime/events':
            try:
                self._stream_runtime_events(parsed)
            except ValueError as exc:
                self._write_json({'ok': False, 'error': str(exc)}, code=400)
            except Exception as exc:
                LOG.exception('Runtime SSE request failed')
                try:
                    self._write_json({'ok': False, 'error': str(exc)}, code=500)
                except Exception:
                    pass
            return

        if parsed.path == '/auto/routes':
            try:
                result = bridge.list_auto_routes()
                self._write_json({'ok': True, 'result': result})
            except Exception as exc:
                self._write_json({'ok': False, 'error': str(exc)}, code=500)
            return

        self._write_json({'ok': False, 'error': 'Not found'}, code=404)

    def _handle_json_write(self, method: str) -> None:
        try:
            data = self._read_json()
            bridge = self._bridge()
            if method == 'PUT' and self.path == '/api/config':
                result = bridge.config_store.replace_config(
                    displays=collection_payload(data, 'displays')['items'],
                    inputs=collection_payload(data, 'inputs')['items'],
                    bindings=collection_payload(data, 'bindings')['items'],
                )
                self._write_json({'ok': True, 'result': config_payload(result)})
                return

            if self.path == '/mqtt/topics/sync':
                broker = str(data.get('broker_host', '')).strip()
                port = int(data.get('broker_port', 1883))
                timeout_s = float(data.get('timeout_s', 3))
                max_topics = int(data.get('max_topics', 1200))
                if not broker:
                    raise ValueError('broker_host is required')
                result = bridge.sync_topics(broker, port, timeout_s, max_topics)
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
                result = bridge.get_topic_value(broker, port, topic, timeout_s, fresh=fresh)
                self._write_json({'ok': True, 'result': result})
                return

            if self.path == '/mqtt/live/start':
                broker = str(data.get('broker_host', '')).strip()
                port = int(data.get('broker_port', 1883))
                if not broker:
                    raise ValueError('broker_host is required')
                result = bridge.start_live(broker, port)
                self._write_json({'ok': True, 'result': result})
                return

            if self.path == '/mqtt/live/stop':
                broker = str(data.get('broker_host', '')).strip()
                port = int(data.get('broker_port', 1883))
                if not broker:
                    raise ValueError('broker_host is required')
                result = bridge.stop_live(broker, port)
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
                result = bridge.live_snapshot(broker, port, query=query, limit=limit, auto_start=auto_start)
                self._write_json({'ok': True, 'result': result})
                return

            if self.path == '/auto/routes/replace':
                display_ip = str(data.get('display_ip', '')).strip()
                routes = data.get('routes', [])
                result = bridge.replace_auto_routes(display_ip=display_ip, routes=routes)
                self._write_json({'ok': True, 'result': result})
                return

            if self.path == '/api/display/update':
                ip = str(data.get('ip', '')).strip()
                result = bridge.display_updates.trigger_update(ip)
                self._write_json({'ok': True, 'result': result})
                return

            if self.path == '/api/display/update/start':
                ip = str(data.get('ip', '')).strip()
                result = bridge.display_updates.start_update_job(ip)
                self._write_json({'ok': True, 'result': result})
                return

            self._write_json({'ok': False, 'error': 'Not found'}, code=404)
        except TimeoutError as exc:
            self._write_json({'ok': False, 'error': str(exc)}, code=504)
        except Exception as exc:
            LOG.exception('Request failed')
            self._write_json({'ok': False, 'error': str(exc)}, code=400)

    def do_POST(self) -> None:
        self._handle_json_write('POST')

    def do_PUT(self) -> None:
        self._handle_json_write('PUT')

    def log_message(self, fmt: str, *args: Any) -> None:
        LOG.info('%s - %s', self.client_address[0], fmt % args)


class BridgeHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_cls, bridge: MQTTBridge) -> None:
        self.bridge = bridge
        super().__init__(server_address, handler_cls)


def build_server(
    host: str,
    port: int,
    *,
    app_config_path: str | None = None,
    auto_rules_path: str | None = None,
    start_discovery: bool = True,
    start_thread: bool = True,
) -> tuple[BridgeHTTPServer, threading.Thread | None]:
    bridge = MQTTBridge(app_config_path=app_config_path, auto_rules_path=auto_rules_path, start_discovery=start_discovery)
    server = BridgeHTTPServer((host, port), Handler, bridge)
    thread = None
    if start_thread:
        thread = threading.Thread(target=server.serve_forever, name='mqtt-bridge-http', daemon=True)
        thread.start()
    return server, thread


def main() -> None:
    parser = argparse.ArgumentParser(description='MQTT helper bridge for AWTRIX webapp')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8090)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    server, _ = build_server(args.host, args.port, start_thread=False)
    LOG.info('Starting MQTT bridge on %s:%s', args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            server.bridge.shutdown()
        except Exception:
            pass
        server.server_close()


if __name__ == '__main__':
    main()
