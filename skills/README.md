# Built-in Skills

This project treats external system integrations as built-in `skills`.

A skill is responsible for:
- defining its own configuration
- resolving a normalized value
- documenting its purpose and usage

A skill is **not** responsible for AWTRIX delivery behavior.

Delivery is generic and shared across skills:
- send mode
- display duration
- template
- display assignment

## Contributing a New Skill

New skills are added by pull request.

A built-in skill should provide:
- a clear purpose
- a stable config shape
- a documented normalized output
- frontend editor support if needed
- backend/runtime handling if live data is involved
- tests for normalization and runtime behavior

## Current Built-in Skills

- `text`
- `mqtt`
