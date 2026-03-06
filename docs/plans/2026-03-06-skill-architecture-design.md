# Skill Architecture Design

## Problem

The product currently presents `text` and `mqtt` as hard-coded input types. Configuration for data acquisition and display delivery is partially mixed together, especially for MQTT auto-send. That makes contributions harder, blurs the user model, and makes the display pipeline less reusable.

## Goal

Turn the project into a modular, skill-based AWTRIX bridge where contributors can add new built-in skills through pull requests, while keeping display delivery generic and independent from the originating skill.

## Chosen Direction

Use repo-defined built-in skills with a shared contract and a generic delivery layer.

This means:
- `Inputs` become `Skills` in product language and repo structure.
- `text` and `mqtt` become the first built-in skills.
- skill-specific config is separated from generic delivery config.
- bridge auto-routing is generated from normalized skill output + generic delivery policy.
- contributors add new skills inside the repo instead of loading external runtime plugins.

## Core Model

### Skill Definition
A skill is a source of information or content. It owns:
- identity (`kind`, `name`, metadata)
- skill-specific configuration
- preview/runtime value resolution
- documentation for contributors

### Delivery Policy
Delivery policy is generic and reusable across skills. It owns:
- send mode (`off`, `realtime`, `1s..10s`)
- display duration (`1s..10s`, later `until-change`)
- output template

### Binding
A binding maps one skill to one or more displays and can later be extended with enable/disable or priorities.

## Runtime Flow

1. A skill produces a normalized output value.
2. Delivery policy decides if and when that value is pushed.
3. The bridge formats and sends a generic AWTRIX notification.

This keeps the AWTRIX delivery path independent from MQTT, text, or future skill types.

## Repository Model

Add a visible `skills/` section to the repository with:
- `skills/README.md`
- `skills/text/README.md`
- `skills/mqtt/README.md`

README should present the project as a modular skill-based bridge and explicitly invite contributors to add new skills by pull request.

## Migration

The migration should keep current functionality working:
- existing saved `text` and `mqtt` items still load
- UI language shifts from `Inputs` to `Skills`
- existing MQTT/text behavior is mapped into the new generic delivery shape
- bridge route generation uses the new generic model but remains behavior-compatible

## Testing

Backend tests:
- config normalization/migration for legacy items
- generic route generation from skill + delivery config

Frontend tests:
- skills view renders built-in skill cards
- editor mapping still works for `text` and `mqtt`
- save/binding behavior survives rename and restructuring

