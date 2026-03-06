# Dashboard Battery Status Design

## Goal

Show the current battery level for each display directly in the dashboard in a compact, useful way.

## Device Reality

The live AWTRIX stats payload exposes:
- `bat`
- `bat_raw`

It does not expose a clearly named `usb`, `charging`, or `external_power` field on the current devices.

## Chosen UX

Add a compact battery pill to dashboard display cards and the display drawer.

Behavior:
- show percentage if available, for example `47%`
- map percentage to tone buckets for quick scanning
- show a small power indicator only when there is a conservative reason to do so

## Charging Indicator

Because the payload does not expose an explicit charging flag, the UI must not invent a strong charging claim.

For now:
- show a small `power` marker only if battery is `100%`
- treat this as a subtle external-power hint, not a hard charging truth
- if no reliable signal exists, show only the battery value

## Runtime Model

Extend display runtime state with:
- `batteryLevel`
- `batteryRaw`
- `externalPowerHint`

Populate them from `/api/stats`.

## Testing

- runtime store test verifies battery extraction from stats
- dashboard card test verifies battery label rendering
- optional drawer test verifies the same metadata is visible in details

