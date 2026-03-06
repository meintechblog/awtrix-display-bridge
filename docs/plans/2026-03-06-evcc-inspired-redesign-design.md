# EVCC-Inspired Redesign Design

**Date:** 2026-03-06  
**Status:** Approved  
**Reference:** [evcc-io/evcc](https://github.com/evcc-io/evcc), [evcc.io](https://evcc.io/)

## Goal

Rebuild the current AWTRIX web application as a `dashboard-first`, EVCC-inspired product UI that preserves the existing Python MQTT/AWTRIX runtime while replacing the single-file frontend with a structured Vue/Vite application.

## Product Direction

- `dashboard-first` instead of form-first
- `true multi-display` as the core model in V1
- `reusable inputs` that can be assigned to multiple displays
- `drawer/modal editing` instead of page-heavy configuration flows
- `existing Python bridge` remains the runtime core
- `feature parity first`, deeper modules later

## Information Architecture

The new app treats the dashboard as the default operating surface.

- `Dashboard` is the landing view and primary work area.
- A global summary row surfaces system health at a glance:
  - number of displays
  - online/offline counts
  - last runtime activity
  - broker/runtime health
  - active issues
- Below the summary, display cards become the main unit of interaction.
- Each display card exposes the live state directly:
  - display name
  - IP address
  - online status
  - embedded live preview
  - active content
  - quick actions such as `Clear`, `Send test`, `Pause`
  - assigned inputs with status chips
- Detailed editing opens in side drawers so the user stays in runtime context.
- Lower-frequency administrative concerns move into a separate settings area.

## Core Domain Model

### Display

Represents one physical AWTRIX target.

Attributes:
- id
- name
- ip
- status metadata
- preview URL
- default delivery behavior

### Input

Represents one reusable content source.

Initial types:
- `text`
- `mqtt`

Future types can include:
- `http`
- `schedule`
- `preset`
- `rule-driven`

### Binding

Connects an input to one or more displays.

Attributes:
- display targets
- input reference
- delivery configuration
- enablement state

### Delivery Policy

Defines when and how values are sent to the display.

Examples:
- `realtime`
- `1s..10s`
- `off`
- display duration
- until-change behavior
- stale guard

### Runtime State

Represents live operational state and is kept distinct from persisted configuration.

Examples:
- MQTT connection status
- last seen topic value
- last send timestamp
- last delivery error
- stream health
- preview freshness

## UX Principles

The UI should be close to EVCC in behavior and hierarchy, not as a visual clone.

- Data first, forms second.
- High signal density without visual clutter.
- Dark mode by default with deep charcoal surfaces instead of flat black.
- Strong card layout, generous spacing, clear semantic colors.
- Minimal explanatory copy.
- Status should be legible from a distance.
- Mobile should use stacked cards and bottom-sheet style editing, not compressed desktop layouts.

## UI Composition

### App Shell

- Vue application shell with responsive navigation
- dashboard-centered main content area
- compact top-level navigation for:
  - `Dashboard`
  - `Displays`
  - `Inputs`
  - `Settings`

### Dashboard

- top summary section
- grid of display cards
- each card independently useful without opening a details page

### Display Detail

Opened in a drawer or modal panel and contains:
- editable display metadata
- live preview
- quick actions
- assignment overview
- runtime diagnostics

### Input Library

Inputs are presented as structured building blocks instead of loose form blocks.

- `Text` inputs focus on content and presentation
- `MQTT` inputs focus on source, topic, extraction path, latest value, auto-send state

### MQTT Topic Browser

The browser must support progressive discovery.

- hierarchical drilldown
- search
- visible current value
- clear path selection
- no giant flat topic dump

## Technical Architecture

## Frontend

- `Vue 3`
- `Vite`
- `vue-router`
- `Pinia`
- component-driven UI structure
- design tokens for colors, spacing, radius, and state semantics

Planned component families:
- `AppShell`
- `DashboardSummary`
- `DisplayCard`
- `DisplayDrawer`
- `InputLibrary`
- `InputCard`
- `InputEditor`
- `TopicBrowser`
- `StatusBadge`

## Backend

The Python bridge remains the runtime core.

Responsibilities retained:
- MQTT subscriptions and topic discovery
- server-side auto-routing
- AWTRIX delivery
- configuration persistence

A cleaner application API layer is added in front of the runtime:
- `/api/dashboard`
- `/api/displays`
- `/api/inputs`
- `/api/bindings`
- `/api/runtime/events`
- `/api/topics/browser`

The frontend should not depend on internal bridge implementation details.

## State Model

Separate state buckets:

- `Config State`
  - persisted displays, inputs, bindings, defaults
- `Runtime State`
  - online/offline status, last topic values, send status, stream health
- `Derived View State`
  - card-level summaries composed from config and runtime

## Live Data Flow

- persisted configuration is loaded and saved via REST-like API endpoints
- runtime updates are streamed via SSE first
- browser state subscribes to runtime events but does not own auto-send execution
- all auto-send logic remains server-side so the system works without an open browser

## Error Handling

The product should expose actionable operational state, not just transient notifications.

State categories:
- `online`
- `degraded`
- `offline`
- `config error`

Principles:
- errors are shown at the affected card or drawer
- stream reconnect state is visible
- stale runtime data is explicitly marked
- runtime outages do not collapse the UI

## Migration Strategy

### Phase 1

Add a clean application API layer on top of the current Python bridge.

### Phase 2

Build the new Vue/Vite frontend in parallel with the current single-file frontend.

### Phase 3

Reach feature parity for the existing user-visible capabilities:
- display management
- live preview
- text inputs
- MQTT inputs
- topic browser
- server-side auto-send
- clear action
- save/draft behavior

### Phase 4

Switch the deployed web UI to the new frontend and keep the old interface as fallback until the cutover is stable.

## MVP Scope

Included:
- multi-display dashboard
- display cards with live preview and quick actions
- input library with `text` and `mqtt`
- reusable bindings between inputs and displays
- hierarchical MQTT topic browser with search
- server-side auto-send configuration
- explicit draft/save UX
- dark default theme

Excluded from MVP:
- history
- presets
- scenes
- advanced automation rules
- user management
- analytics

## Success Criteria

The redesign is successful when:

- the app feels like an operational dashboard rather than a configuration page
- multi-display is a first-class concept throughout the UI
- MQTT and AWTRIX runtime behavior remains browser-independent
- the new structure supports later modules without another UX rewrite
- the visual and interaction quality is materially closer to EVCC than the current MVP UI
