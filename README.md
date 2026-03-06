# AWTRIX Skill Bridge

A modular AWTRIX display bridge with a dashboard-first web UI, built-in skills, and generic delivery policies.

## Core Idea

This project separates two concerns:
- `Skills` fetch or produce values from external systems
- `Delivery` decides how those values are sent to AWTRIX displays

That keeps the display pipeline generic while making integrations easy to extend.

## Built-in Skills

- `Text Skill`
- `MQTT Skill`

See [skills/README.md](skills/README.md) for the contribution model.

## Contributing

Want to connect another system?

Add a new built-in skill and open a pull request.

A new skill should define:
- its own config shape
- how it resolves a normalized value
- how it is presented in the UI
- tests for config/runtime behavior

## Features

- Dark-mode dashboard web UI
- Multi-display configuration
- Built-in skill library (`text`, `mqtt`)
- Hierarchical MQTT topic browser
- Generic delivery policy per skill
- Server-side MQTT auto-routing without open browser tab
- Display live screen embed via clean renderer (`/live.html`)
- Firmware version checks and async update jobs
- Always-on display discovery in local subnets

## Repository Layout

- `ui/` - Vue/Vite dashboard application
- `bridge/` - Python runtime bridge and APIs
- `skills/` - built-in skill definitions and contributor docs
- `frontend/live.html` - clean AWTRIX live renderer
- `deploy/systemd/` - deployment units
- `tests/` - Python regression tests

## Runtime Architecture

- Browser UI talks to the bridge API on port `8090`
- Built-in skills resolve values from configured sources
- Generic delivery policies transform skill outputs into AWTRIX notifications
- MQTT live sessions are kept server-side
- Auto-routes continue to run when no browser is open

## Requirements

- Python `3.11+`
- `paho-mqtt`
- Node.js `20+` for UI build

## Quick Start (Debian)

```bash
apt update
apt install -y python3 python3-pip nodejs npm
pip3 install -r requirements.txt

mkdir -p /opt/ulanzi-bridge /var/www/ulanzi
cp -r bridge /opt/ulanzi-bridge/
cp deploy/systemd/ulanzi-mqtt-bridge.service /etc/systemd/system/
cp deploy/systemd/ulanzi-web.service /etc/systemd/system/
cp -r ui/dist/* /var/www/ulanzi/
cp frontend/live.html /var/www/ulanzi/live.html

systemctl daemon-reload
systemctl enable --now ulanzi-mqtt-bridge.service ulanzi-web.service
```

## Bridge API

- `GET /health`
- `GET /api/config`
- `GET /api/dashboard`
- `GET /api/displays`
- `GET /api/inputs`
- `GET /api/bindings`
- `GET /api/topics/browser`
- `GET /api/topics/value`
- `GET /api/display/update-status`
- `POST /api/display/update/start`
- `GET /api/display/update/job`
- `POST /auto/routes/replace`

## Notes

- The persisted config still uses the `inputs` key for backward compatibility, but the product surface now treats them as skills.
- Delivery behavior is normalized through shared fields instead of being owned by one specific skill type.
