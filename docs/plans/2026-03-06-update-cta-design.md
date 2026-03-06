# Update CTA Consolidation Design

**Date:** 2026-03-06  
**Status:** Approved

## Goal

Reduce the display firmware UI to one central update element that combines status and action, while keeping the version signal readable and compact.

## Product Decisions

- `Version <current>` remains as a small passive info pill.
- The current `Neueste <version>` + `Update verfügbar` + `Update` combination is replaced by a single central update element.
- The central element carries both the state and the target version when relevant.
- `Webinterface` remains separate because it is a different action.

## CTA States

- update available: clickable CTA `Update verfügbar · <latest>`
- updating: disabled CTA `Update läuft...`
- current: passive badge `Aktuell · <latest>`
- failed after user action: retry CTA `Update fehlgeschlagen`

## UX Notes

- Avoid duplicate version noise in the row.
- Keep follow-up text below the row only for errors or recent action feedback.
- The CTA should remain visually stronger than the passive version pill, but not overload the card.
