# Changelog

## 0.2.20

- **Edge fillet / chamfer on the part's body**, as in CAD tools: a `Fillet` or
  `Chamfer` with no `solid` rounds / bevels the edges of the body built by
  every operation before it (all edges, or those an `EdgeFinder` selects);
  operations added after it apply on top, unrounded. New shortcuts
  `part.fillet_edges(radius, edges=None)` and
  `part.chamfer_edges(distance, edges=None)` (they refuse an empty part).
  `Fillet(solid, radius)` / `part.fillet(solid, ...)` are unchanged.
- `Fillet.solid` and `Chamfer.solid` are now optional.
- Documented semantics (schema docstrings; kernels follow them):
  - `Thicken`: `thickness` along the surface normal (a `PlanarSurface`'s
    normal is its sketch plane's normal); `both_sides=True` puts `thickness`
    on each side (2 × thickness total).
  - `Stitch`: only a closed shell (no free edges) becomes a solid; an open
    one stays a shell.
  - `Loft.guides`: rails the loft surface passes through (each must start on
    the first section's outline and end on the last one's).

## 0.2.19

- `check_interference(exact=True)` no longer reports line-to-line fits (a
  shaft in a same-size bore) as overlaps:
  - the default `kernel_api_mesher` asks for a fine tessellation
    (`FINE_MESH_CONFIG`: 0.01 mm chord, 0.05 rad; override with `mesh_config=`);
  - new `depth_tol` (default `DEFAULT_DEPTH_TOL` = 0.02 mm): shared regions
    thinner than this (2 x volume / area) are ignored, also for custom meshers.
  Real interference is still reported (a 0.1 mm press fit: 50.9 mm³).

## 0.2.18

- **Exact interference check**: `assembly.check_interference(exact=True)`
  compares the real solids instead of bounding boxes — each part is meshed
  (through the kernel API by default, `kernel_api_mesher()`, or your own
  `mesher=`), placed, and every pair's shared volume computed with
  `manifold3d`. Pairs sharing more than `volume_tol` mm³ are reported with
  their volume and depth. Jointed / connected pairs are checked too (a joint
  means the parts touch, not that they may interpenetrate); exempt a pair with
  `allow=[(a, b)]`. Install with `pip install 'cadbuildr-foundation[exact]'`.
  The default bounding-box mode is unchanged.
- `solid_overlap(mesh_a, mesh_b)` helper.

## 0.2.17

Assemblies: anchors, placement, joints and interference.

- **Anchor helpers** (`anchors.py`): `make_anchor(name, position, ...,
  z_axis=, x_axis=)`, `Anchor.linear_pattern` / `polar_pattern` /
  `along_path`, `rotate_deg`, `add_anchors`; derived names are auto-unique.
- **Placement** (`placement.py`): `add_component(comp, at=, rot_deg=)`,
  `assembly.ground(anchor, at=, rot_deg=)`, loop-closing `add_connection`
  (raises `LoopClosureError` when the anchors disagree), hole wizards accept
  an `Anchor`. `Connection.joint` is now optional (modifier-only connections).
- **Joints**: `set_angle` / `set_offset` cascade to everything jointed
  downstream, including inside placed sub-assemblies; `joint.resolve()` and
  `Assembly.resolve()`. A joint in a sub-assembly may take its parent anchor
  from a sibling component (resolved through the common enclosing assembly).
- **Interference**: `assembly.check_interference(tolerance=, allow=, ...)`.
- **Live components**: components placed with `add_component` stay live —
  operations / anchors added afterwards are no longer lost.
- `Polygon.from_points`; `Draft(neutral_plane=)` for tilted neutral planes.
- **Cylinder**: new `centered=` flag. `Cylinder` is
  bottom-anchored (`0..height` along the sketch normal) while `Box` is
  centred. Code written for the old centred cylinder should pass
  `centered=True` (`-height/2..+height/2`) instead of shifting by hand. The
  default is unchanged.

## 0.2.16

Feature-complete CAD operations and sheet metal.

- **Face selection**: `FaceFinder` with `ContainsPointFinderRule` and friends.
- **Operations**: `Emboss` / `Wrap` (raise or engrave a profile onto a curved
  face, `EmbossMode`), `Split`, `Draft`, `Rib`, `Rip`, `OffsetFace`,
  `MoveBody`, `BooleanOperation`, `LinearPattern` / `PolarPattern` nodes,
  `TextOnPath`.
- **Surfaces**: `PlanarSurface`, `ExtrudedSurface`, `RevolvedSurface`,
  `RuledSurface`.
- **Holes**: `ClearanceHole`, tapped-hole updates, `holes` helpers.
- **Sheet metal**: contour flange, cut, bead, dimple, extruded hole,
  sheet-metal-from-solid, fold/lofted-bend updates, material table updates.
- `sketch_ops` helpers; new generated node classes under `gen/models`.

## 0.2.15

- `paint()` / `resolve_color()` accept both spellings of grey: `"gray"`,
  `"dark_gray"`, `"light_bluish_grey"`… now resolve like their `grey`/`gray`
  counterparts instead of raising `Unknown color`.

## 0.2.14

- `KernelApiClient` can talk to a kernel sidecar over a unix socket
  (`coms/kernel_api.py`), alongside the HTTP transport.
- Fix: derived planes (`get_parallel_plane`, `get_angle_plane_from_axis`)
  applied their parent plane's transform twice, so they landed in the wrong
  place on any base plane other than `xy()` (and on chained calls).

## 0.2.13

Assembly interfaces: anchors and joints, schema-first.

- **Anchors** (`Anchor`, `make_anchor`, `anchor_plane`): named mate frames on
  parts (+Z = mate axis / outward normal, +X = clocking), with derivation
  helpers `offset()`, `rotated()`, `flipped()`.
- **Joints**: `RigidJoint`, `RevoluteJoint`, `SliderJoint`,
  `CylindricalJoint`, `PlanarJoint`, `BallJoint`, `PinSlotJoint`,
  `ScrewJoint` (+ `JointLimits`). A joint places exactly one child component
  anchor-to-anchor (mated with a 180° flip about X); DOF setters
  (`set_angle`/`set_offset`) re-resolve the placement.
- **Connections** (`Connection`, `PartModifier`,
  `Assembly.add_connection`): a named joint plus geometry contributions cut
  on the connected parts — the primitive libraries use for joinery
  (mortise & tenon, box corners...).
- `Assembly.add_anchor` / `add_joint` / `ground`; `Part.add_anchor`.
- New generated node classes under `gen/models` for all of the above.

The 0.2.12 wheel on PyPI predates this API even though the source tree
carried the same version for a while — depend on `>=0.2.13` for
anchors/joints.

## 0.2.12

Schema-first rebuild of the sheet-metal operation set — each operation is now a
generated node class (like `Extrusion`/`Lathe`), not a hand-written helper.

- **Sheet metal: nodes, not helpers.** The snake_case wrapper layer
  (`base_flange`, `edge_flange`, `miter_flange`, `hem`, `to_solid`, …) is
  removed. Construct the generated node classes directly:
  `SheetMetalBaseFlange`, `SheetMetalTab`, `SheetMetalEdgeFlange`,
  `SheetMetalMiterFlange`, `SheetMetalHem`, `SheetMetalSketchedBend`,
  `SheetMetalClosedCorner`, `Unfold`, `SheetMetalToSolid`. (`SheetMetalJog`,
  `SheetMetalCornerRelief`, `SheetMetalFold`, `SheetMetalLoftedBend` are
  schema-defined and not yet implemented in the kernel.)
- **Typed enums** for choice inputs (`FlangePosition`, `HemType`, `CornerType`,
  `ReliefType`, `SheetDirection`, …) instead of loose strings.
- **`EdgeRef`** input type with an automatic cast: a node declares
  `edge: EdgeRef!` but accepts a bare `Line` (or an `EdgeFinder` query).
- Removed the old `SheetMetalBend`, `SheetMetalContourFlange`, and
  `SheetMetalCornerSeam` nodes.
- `SheetMetalConfig` / materials helpers are unchanged.

Breaking: code using the old sheet-metal helper functions must migrate to the
node classes. The rest of the foundation API is unchanged.
