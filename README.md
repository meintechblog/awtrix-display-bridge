# AWTRIX Display Bridge

Webapp + MQTT bridge to push dynamic content to an AWTRIX 3 display (Ulanzi).

## Features
- Dark-mode web UI for display configuration
- Input blocks (text + MQTT)
- MQTT topic sync and hierarchical topic browser
- JSON key extraction from payloads
- Manual send + auto-send modes (`real time`, `1s..10s`, `off`)
- Per-block stale guard to drop outdated values
- Display live screen embed (`/screen`)

## Repository Layout
- `frontend/index.html` - Single-file web UI
- `bridge/mqtt_bridge.py` - MQTT helper API (port `8090`)
- `deploy/systemd/ulanzi-mqtt-bridge.service` - Systemd service unit

## Runtime Architecture
- Browser UI talks to AWTRIX device API directly (`http://<display-ip>/api/...`)
- Browser UI talks to bridge API on port `8090` for MQTT operations
- Bridge maintains persistent MQTT live sessions per broker

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
```

## Bridge API
- `GET /health`
- `POST /mqtt/topics/sync`
- `POST /mqtt/topic/value`
- `POST /mqtt/live/start`
- `POST /mqtt/live/stop`
- `POST /mqtt/live/snapshot`

## Notes
- The UI is optimized for low-latency updates and ignores stale MQTT values based on per-block stale guard.
- For predictable behavior, ensure broker and display are on stable LAN.
