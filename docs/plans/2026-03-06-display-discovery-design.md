# Display Discovery Design

**Date:** 2026-03-06  
**Status:** Approved

## Goal

Add always-on server-side AWTRIX/Ulanzi discovery so the app can find displays on the local network continuously and let the user adopt them directly from the `Displays` section.

## Product Decisions

- Discovery scans only the Debian server's local private subnets automatically.
- Discovery starts with the bridge service and runs continuously in the background.
- Scan cadence is `30s`.
- Already configured displays are excluded from discovery results.
- `Adoptieren` creates a local unsaved draft display.
- The existing explicit save flow remains authoritative:
  - adopt
  - review/edit if needed
  - `Speichern`

## UX

The `Displays` page keeps the existing configured display list and adds a compact discovery section above it.

Discovery section content:
- scan status
- short error text if scan fails
- cards for found but not-yet-added displays

Discovery card content:
- IP
- friendly name or hostname if available
- AWTRIX metadata when available:
  - version
  - active app
  - Wi-Fi signal
  - matrix state
- `Adoptieren`

Adoption behavior:
- creates a display draft in the normal display configuration list
- immediately removes the device from discovery results
- marks global config state as `Ungespeichert`
- user persists through the existing save button

Discard behavior:
- if the user discards unsaved changes, the adopted draft disappears again
- the device can reappear in discovery

## Backend Architecture

Discovery is server-side, not browser-side.

New backend responsibilities:
- detect local private IPv4 subnets from active interfaces
- scan hosts in those subnets with bounded concurrency
- probe AWTRIX candidates via short HTTP requests to `/api/stats`
- normalize successful responses into lightweight discovery records
- update a rolling discovery cache every `30s`
- filter out displays already present in persisted configuration

Planned API surface:
- `GET /api/discovery/displays`
  - returns current cached results
  - can optionally support `refresh=1` as an override, but the normal UX does not depend on it

## Runtime Constraints

- discovery must not block the rest of the app
- scan timeouts must be short
- concurrency must be bounded
- scan should only include private local subnets
- failure to discover must not affect runtime MQTT/AWTRIX operation
- the worker must keep running independently of any browser session

## Error Handling

- no subnet found: return empty list with error detail
- partial scan failures: still return successful findings
- unreachable hosts: ignored silently
- malformed AWTRIX responses: ignored
- discovery endpoint failure: surfaced in UI without breaking display configuration
- worker failures: retried on the next scheduled scan interval

## MVP Scope

- subnet detection from local interfaces
- parallel AWTRIX HTTP scan
- always-on background worker with cached current results
- discovery API
- discovery UI in `Displays` without requiring user interaction
- adopt into unsaved config
- exclude already configured displays

## Out of Scope

- manual CIDR entry
- mDNS/Bonjour
- auto-adopt
- extra device-management actions beyond adoption
