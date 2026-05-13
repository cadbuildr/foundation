# CADbuildr Foundation

## Summary

Schema-driven Python types for CAD modeling, generated from the GraphQL foundation schema.

## Tags

cad, python, foundation, schema

## Status

green

## Guidelines

- Keep generated code deterministic and reproducible across machines.
- Avoid manual edits in generated modules; change the schema instead.
- Keep public APIs stable and document migrations when needed.

## Dependencies

### Upstream

- (none)

### Downstream

- (none)

## Notes

See `/schemas/foundation/` for schema definition.

## Kernel API Contract

- Canonical render endpoint: `POST /v1/kernels/:kernel/render` with `format=json|stl|step`.
- Foundation direct compile endpoint env: `CAD_COMPILE_API_BASE_URL`.

## Local viewer and screenshots (broker)

For interactive `show(...)` plus Hub viewer screenshots, use the local broker and the broker–viewer setup docs in the monorepo (`docs` / `threepointo` resources, or the broker package README in this repository).

**Python helpers** (from the installed Foundation package):

- `request_viewer_screenshot(...)` — POST to the broker with `framing` and return the JSON body.
- `build_screenshot_framing(...)` — build the `framing` dict (`view`, optional `zoom`, `camera_position`, `target`, `up`; `plane` is accepted as a legacy alias for `view`).

**CLI (`get-screenshot` / `get_screenshot_main`):** `--view` (`iso`, `current`, orthographic presets), `--plane` (alias), `--zoom`, and optional `--camera X Y Z`, `--target X Y Z`, `--up X Y Z` with `--broker-url` and `-o` output path.

See the broker package README for the raw `POST /screenshot/request` JSON contract.
