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

`cadbuildr/foundation/gen/` is generated from the CADbuildr foundation GraphQL schema and shipped prebuilt in this repository; do not edit it by hand.

## Kernel API Contract

- Canonical render endpoint: `POST /v1/kernels/:kernel/render` with `format=json|stl|step`.
- Foundation direct compile endpoint env: `CAD_COMPILE_API_BASE_URL`.

## Local viewer and screenshots (broker)

For interactive `show(...)` plus Hub viewer screenshots, use the local CADbuildr broker and its README.

**Python helpers** (from the installed Foundation package):

- `request_viewer_screenshot(...)` — POST to the broker with `framing` and return the JSON body.
- `build_screenshot_framing(...)` — build the `framing` dict (`view`, optional `zoom`, `camera_position`, `target`, `up`; `plane` is accepted as a legacy alias for `view`).

**CLI (`get-screenshot` / `get_screenshot_main`):** `--view` (`iso`, `current`, orthographic presets), `--plane` (alias), `--zoom`, and optional `--camera X Y Z`, `--target X Y Z`, `--up X Y Z` with `--broker-url` and `-o` output path.

See the broker package README for the raw `POST /screenshot/request` JSON contract.

## Interference check

`assembly.check_interference(tolerance=0.0, allow=[...], strict=False)` returns
`Interference` records (two component paths, overlap `depth` mm, `volume`
estimate mm³, or `status="unknown"`). It runs a separating-axis test on
oriented bounding boxes estimated from each part's operations (sketch bounds ×
extrusion/revolve extents, exact rectangular cuts carved out) and placed with
the live component transforms. Joints, `add_connection` connections (including
loop closures and modifier-only ones) and `allow` pairs are intended contacts.
Parts that cannot be bounded are reported as unknown; declare them with
`part.set_extents(OBB | (lo, hi))` or `extents={...}`. `OBB` /
`obb_intersects` are the shared primitives for libraries (woodworking's
occupancy check can delegate to them). See `cadbuildr/foundation/interference.py`.

## Component introspection (public API)

Use these instead of the private helpers (which keep working as aliases):

| Public | Replaces | What it gives |
|---|---|---|
| `owner_of(anchor_or_interface)` | `compute_functions._anchor_owner` | the Part / Assembly that owns it |
| `source_of(placed_root)` | the `_source_component` attribute | the live Python Part / Assembly behind `assembly.components[i]` |
| `component_extents(component)` | `interference._walk` | `ComponentExtents(lo, hi, boxes, unknown)` in the component's own frame; `.size`, `.center`, `.known` |

`component_extents` bounds `Text` with a font-free outer estimate (glyph
advance ≤ 1 em, ascender 1 em, descender 0.3 em); `check_interference` still
reports Text parts as unknown (`estimate_part_extents(part, text=True)` opts in).

Placement and geometry helpers:

- `assembly.ground(part, at=(x, y, z), rot_deg=...)` or
  `ground(part, z_axis=(...), x_axis=(...), at=...)` grounds the first
  component at a pose (an anchor / interface accepts `z_axis=` too).
- `scale_about(shape, factor, center)` scales a solid about a point
  (`MoveBody` → `Scale` → `MoveBody`; `Scale` alone scales about the part origin).
- `plane_from_normal(part, origin, normal, x_dir=None)` is a sketch plane that
  hangs from the part's frame.
- `self.head = ...` is allowed on a Part / Assembly (it shadows the legacy
  `.head.frame` alias); assigning any other read-only foundation property
  raises an `AttributeError` that names it.

## Design checks (`check()`, `__checks__`, reports)

Every check returns issues shaped `{severity, code, interfaces, components,
delta, message, fix}` (`severity`: `error` / `warning` / `info`); the viewer's
Check panel reads them from `show_dag(obj)["checks"]`.

- Libraries add their own (printability, sheet-metal / moulding DFM, geometric
  checks) with a `__checks__()` method on any Part or Assembly class, returning
  `issue(...)` dicts, `Report`s or strings. Check the real geometry, not a
  simplified stand-in: the hook runs on the actual component.
- Code that is not a method (an `@operation`, a rule) attaches findings with
  `add_check(component, issue_or_report)` or `Report(...).attach(component)`;
  an `@operation` may return `(geometry, report)`.
- `part.check()` and `assembly.check()` collect the whole tree (sub-assemblies
  included, nested components named by path `sub/part`);
  `assembly.check(recursive=False)` keeps only the assembly's own interface
  checks. `collect_checks(obj)` is the function behind both and `show_dag`.
- Mate rules report non-fatal findings with `ctx.warn(code, message)`;
  `screw_in_hole` warns `thread_engagement` / `thread_bottoms_out` for tapped
  holes (`interfaces.rules.thread_engagement` is the helper).
- An assembly's `frame` keeps working as the reference of
  `tf_relative_to_frame` / `check_interference` after it is nested or
  serialised (`math_utils.frame_aliases`).

## Source locations on DAG nodes (opt-in)

So a viewer edit can be mapped back to the line of Python that produced it,
each node can carry where it was built in user code:

```jsonc
{ "type": 12, "params": {}, "deps": { "end": "a1f3", "shape": ["9bb9"] },
  "src":      { "file": "parts/bracket.py", "line": 42, "col": 23, "endCol": 40, "text": "Extrusion(sq, 10)" },
  "fieldSrc": { "end":   { "file": "parts/bracket.py", "line": 42, "col": 37, "endCol": 39, "text": "10" },
                "shape": { "file": "parts/bracket.py", "line": 42, "col": 33, "endCol": 35, "text": "sq" } } }
```

- `src` is the call expression in the first frame outside the `cadbuildr`
  packages, pydantic and the stdlib; `fieldSrc` maps each field the caller
  supplied to that argument's span and source text (`"10"`, `"width"`,
  `"width * 2"`). Arguments map to fields by keyword, by the called function's
  parameter names, then by value; unmatched arguments are left out.
- `line` is 1-based, `col`/`endCol` are 0-based character offsets (`endCol`
  exclusive, only for single-line spans). `file` is relative to
  `source_capture.set_root()` / `CADBUILDR_SOURCE_ROOT` / the cwd when under it.
- Nodes are deduplicated by content, so a shared `FloatParameter(10)` is one
  node; per-use locations live on the owner's `fieldSrc`. `src`/`fieldSrc` are
  added after hashing: node ids are identical with capture on or off.

Locations are recorded at construction, so turn capture on **before** the
model code runs: `CADBUILDR_WITH_SOURCE=1` (read at import), or
`cadbuildr.foundation.source_capture.enable()` / `with capturing():` in the
runtime that executes user code. `show(...)` / `show_dag(...)` take
`with_source: bool | None` (`None` follows the capture switch); `to_dag_method`
takes `with_source=False`. Never enabled means nothing is installed; disabled
costs one flag check per model. Capture never raises. Columns and `fieldSrc`
need Python 3.11+ (3.10: `file` + `line` only); `exec`'d code needs a real
filename visible to `linecache`. See `cadbuildr/foundation/source_capture.py`.
