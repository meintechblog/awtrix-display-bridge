# Display Version and Update Design

**Date:** 2026-03-06  
**Status:** Approved

## Goal

Show each configured AWTRIX display's current firmware version in the `Displays` section, compare it with the latest official AWTRIX release, and offer a best-effort update trigger directly from the app.

## Product Decisions

- Version status is shown per configured display, not in discovery cards.
- The latest official version is checked server-side against the official AWTRIX GitHub `version` file.
- The bridge caches the latest-version lookup to avoid repeated GitHub requests.
- `Update verfügbar` is based on server-side version comparison, not on the device's own OTA self-check.
- The update action is labeled `Update versuchen` because the AWTRIX `/api/doupdate` endpoint is not reliable enough to promise a guaranteed one-click update.
- A direct link to the device webinterface stays available as fallback.

## UX

Each configured display card gets a compact firmware row:
- current version
- latest known official version when available
- `Update verfügbar` badge when the latest version is newer
- `Update versuchen` action
- `Webinterface` action

Action semantics:
- version info is read-only runtime state
- `Update versuchen` triggers the AWTRIX OTA endpoint once and returns the device response
- failures are shown honestly; they are not translated into a false `kein Update`

## Backend Architecture

The bridge gets a small display-update service layer:
- fetch latest official AWTRIX version from GitHub
- cache the result for a fixed TTL
- fetch a display's current version from `/api/stats`
- compare versions server-side
- forward `POST /api/doupdate` to the target display as a best-effort trigger

Planned API surface:
- `GET /api/display/update-status?ip=<ip>`
- `POST /api/display/update`

## Error Handling

- latest-version lookup failure: keep current version, surface error, do not guess update availability
- display stats failure: surface error for that display only
- OTA trigger failure: return the actual device response/status
- GitHub or network failures must not affect MQTT or the rest of the UI

## Scope

- server-side version comparison with cache
- per-display firmware status in UI
- best-effort update trigger
- direct webinterface fallback button

## Out of Scope

- automatic firmware rollout
- forced update retries
- batch updates across displays
- release notes UI
