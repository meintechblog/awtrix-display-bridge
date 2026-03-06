# AWTRIX Display Bridge

Webapp + MQTT bridge to push dynamic content to an AWTRIX 3 display (Ulanzi).

## Features
- Dark-mode web UI for display configuration
- Input blocks (text + MQTT)
- MQTT topic sync and hierarchical topic browser
- JSON key extraction from payloads
- Manual send + auto-send modes (`real time`, `1s..10s`, `off`)
- Per-block stale guard to drop outdated values
- Event-driven MQTT forwarding via SSE (no polling loop)
- Server-side auto-routing (runs without open browser)
- Display live screen embed via clean renderer (`/live.html`)

## Repository Layout
- `frontend/index.html` - Single-file web UI
- `frontend/live.html` - Clean AWTRIX live renderer (no AWTRIX UI controls)
- `bridge/mqtt_bridge.py` - MQTT helper API (port `8090`)
- `deploy/systemd/ulanzi-mqtt-bridge.service` - Systemd service unit
- `tests/test_mqtt_bridge.py` - Bridge unit tests

## Runtime Architecture
- Browser UI talks to AWTRIX device API directly (`http://<display-ip>/api/...`)
- Browser UI talks to bridge API on port `8090` for MQTT operations
- Bridge maintains persistent MQTT live sessions per broker
- Browser auto-send uses `GET /mqtt/live/events` (SSE) with per-topic stream filters
- Auto-routes are persisted in bridge service and keep forwarding even when no browser is open

## Requirements
- Python `3.11+`
- `paho-mqtt`
- Web server for static frontend (e.g. nginx, caddy, python `http.server`)

## Quick Start (Debian)
```bash
# 1) Install deps
apt update
apt install -y python3 python3-pip
pip3 install -r requirements.txt

# 2) Deploy bridge
mkdir -p /opt/ulanzi-bridge
cp bridge/mqtt_bridge.py /opt/ulanzi-bridge/mqtt_bridge.py
chmod +x /opt/ulanzi-bridge/mqtt_bridge.py

# 3) Deploy service
cp deploy/systemd/ulanzi-mqtt-bridge.service /etc/systemd/system/ulanzi-mqtt-bridge.service
systemctl daemon-reload
systemctl enable --now ulanzi-mqtt-bridge.service

# 4) Deploy frontend (example nginx docroot)
mkdir -p /var/www/ulanzi
cp frontend/index.html /var/www/ulanzi/index.html
cp frontend/live.html /var/www/ulanzi/live.html
```

## Bridge API
- `GET /health`
- `GET /auto/routes`
- `GET /mqtt/live/events` (SSE)
- `POST /auto/routes/replace`
- `POST /mqtt/topics/sync`
- `POST /mqtt/topic/value`
- `POST /mqtt/live/start`
- `POST /mqtt/live/stop`
- `POST /mqtt/live/snapshot`

## Notes
- The UI is optimized for low-latency updates and ignores stale MQTT values based on per-block stale guard.
- For predictable behavior, ensure broker and display are on stable LAN.
- MQTT itself has no universal \"list all topics\" RPC; sync is based on topics seen by the live session.
