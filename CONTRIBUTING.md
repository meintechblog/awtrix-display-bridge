# Contributing

## Development Basics
- Keep frontend changes in `frontend/index.html`
- Keep MQTT bridge changes in `bridge/mqtt_bridge.py`
- Keep deployment assets in `deploy/`

## Validate Before Push
```bash
python3 -m py_compile bridge/mqtt_bridge.py
grep -qi '<!doctype html>' frontend/index.html
```

## Commit Style
- Use clear, imperative commit messages
- Keep each commit focused on one concern
