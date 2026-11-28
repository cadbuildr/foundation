# Changelog

## 0.3.0

Synced from the CADbuildr monorepo (Nov-27). Libraries built for this release
pin `cadbuildr-foundation>=0.3.0,<0.4.0`.

**Design checks: `__checks__` hook, reports, recursive `check()`**
- Any Part or Assembly class can define `__checks__()` and return `issue(...)` dicts, `Report`s or strings. Libraries use it for printability, DFM and fit checks. Do not override `check()`.
- Code that is not a method (an `@operation`, a rule) attaches findings with `add_check(component, issue_or_report)` or `Report(...).attach(component)`. An `@operation` may return `(geometry, report)`.
- `part.check()` and `assembly.check()` collect the whole tree. Nested components are named by path (`sub/part`). `assembly.check(recursive=False)` keeps only the assembly's own interface checks. `collect_checks(obj)` is the function behind both.
- `show_dag(obj)["checks"]` carries the issues for parts and assemblies. Each issue has the shape `{severity, code, interfaces, components, delta, message, fix}`.
- Mate rules can warn without failing (`ctx.warn`). `screw_in_hole` warns `thread_engagement` and `thread_bottoms_out` for tapped holes; the reusable helper is `interfaces.rules.thread_engagement`.
- Fix: an assembly's `frame` still chains after it is nested or serialised (`math_utils.frame_aliases`). Before this, `tf_relative_to_frame(x, asm.frame)` and `check_interference(asm)` raised "does not chain up to frame origin".

**Public component API**
- `owner_of(anchor_or_interface)`, `source_of(placed_root)` and `component_extents(component)`, which returns `ComponentExtents(lo, hi, boxes, unknown)`. They replace the private helpers `compute_functions._anchor_owner`, the `_source_component` attribute and `interference._walk`.
- `assembly.ground(part, at=..., rot_deg=...)`, or `z_axis=` / `x_axis=`, grounds a component at a pose.
- New helpers: `scale_about(shape, factor, center)` and `plane_from_normal(part, origin, normal, x_dir=None)`.
- `self.head = ...` is allowed on a Part or Assembly.
- Component names stay in sync after placement.
- Fix: `check_interference` handles identical parts on free planes and after `show()`.

**Compact DAG geometry**
- `CompactPolygon` / `CompactPolyline` keep a whole outline in one node: flat coordinates, plus an optional bulge per edge for true arcs. `bulge_from_sweep` converts a sweep angle to a bulge. Bad input raises `CompactProfileError`.
- `hole_pattern(...)` turns a `GridLocations` into one hole plus a `LinearPattern`, or a list of points into one multi-circle cut.
- `ring(...)` makes an annulus or groove as one thin-wall `Extrusion`.

**Joints and interfaces** (`cadbuildr.foundation.interfaces`, new)
- Typed mating sites: `ScrewHole`, `ScrewHead`, `Shaft`, `Bore`, `BearingSeat`, `RodHole`, `NemaFace`, `TSlot`, `PlaneFace`, `PivotPin` / `PivotHole`, `SlideRail` / `SlideCarriage`, `StructuralEnd`, … Subclass `Interface` to add more; `clock_symmetry=n` is supported.
- Add one with `part.add_interface(...)`. `assembly.connect(a, b, limits=(lo, hi), clock=k, **dof_or_options)` picks the joint from the mate-rule table (`@mate_rule`, `Mate` with `at` / `rotate` for computed placement, `export_rules()`). `assembly.check()` reports interfaces left unconnected, parts placed by coordinates and loops that no longer close.
- Hole wizards take `fastener=`: `TappedHole` binds a threaded `ScrewHole` and `ClearanceHole` binds a clearance one. New features `RodHole`, `BearingPocket`, `NemaMount` and `ShaftFeature`.
- Assembly patterns copy the relations that drive the patterned joint.
- Joint DOF and sketch-dimension fields are documented in rad / mm (`@unit` in the schema).

**Also in this release**
- Sketch constraints (opt-in): `sketch.constrain([...])` with `Coincident`, `Horizontal`, `Vertical`, `Parallel`, `Perpendicular`, `Tangent`, `Equal`, `Fix`, `Distance`, `HorizontalDistance`, `VerticalDistance`, `Radius`, `Diameter`, `Angle`, `Concentric` and `PointOnLine`. They are solved into plain coordinates when the sketch is serialised, so kernels are unchanged.
- Libraries (`cadbuildr.foundation.library`): `@part` / `@assembly` / `@operation` decorators with typed inputs (`Num`, `OneOf`, `Color`, `InputOf`). Libraries are discovered through the `cadbuildr.libraries` entry point and listed in a manifest. The CLI (`python -m cadbuildr.foundation.library`) provides eval / insert / sources. `PartRoot` / `AssemblyRoot` gain an optional `library: LibraryRef`.
- Source locations on DAG nodes (opt-in): with `CADBUILDR_WITH_SOURCE=1` or `source_capture.enable()`, nodes carry `src` / `fieldSrc`. `show` / `show_dag` take `with_source=`. Columns and `fieldSrc` need Python 3.11 or later; on 3.10 only file and line are recorded.

**Backward compatibility**
- Most changes add API. Existing models build to the same DAG node ids: source capture, compact profiles and sketch constraints change nothing unless you use them.
- The private helpers `_anchor_owner`, `_source_component` and `interference._walk` keep working as aliases. Move to `owner_of`, `source_of` and `component_extents`.
- `show_dag` output may contain a new top-level `checks` key. `show()` prints warnings and errors as `check: <severity> <code>: …` lines.
- Assigning a read-only foundation property on a Part or Assembly (`pf`, `live`, …) still raises `AttributeError`. The message now names the property instead of pydantic's "has no setter". `head` is now settable.
- `CompactPolygon` / `CompactPolyline` are serialised as `CustomClosedShape` / `CustomOpenShape` made of Lines and Arcs, so existing kernels render them unchanged.
- The exported mate-rule table is unchanged unless an interface sets `clock_symmetry`.
- The new `library` field on `PartRoot` / `AssemblyRoot` is optional and defaults to `None`.
- `manifold3d` joins the dev dependency group, for the exact-interference tests.
- `Part.check` and `Assembly.check` are new methods. A subclass that already defines its own `check()` still overrides them, but it then skips the `__checks__` / report collection. New code should implement `__checks__` instead.

## 0.2.21

Onshape-parity release: the features below were missing compared with Onshape's Part Studio and Assembly toolbars.

**Parts**
- **Patterns:** `LinearPattern` takes a second direction (`direction2`, `count2`, `spacing2`) to make a grid. New `CurvePattern(shape, path, count, align_to_path=False)` places copies evenly along a 3D path. Without a `shape`, Linear, Polar and Curve patterns repeat the whole body built so far.
- **Bodies:** `DeleteBodies(bodies)` / `KeepBodies(bodies)` (`part.delete_bodies`, `part.keep_bodies`).
- **Fillets and chamfers:**
  - variable fillet through radius control points: `Fillet.radius_points`, or `fillet_edges(..., radius_points=[(0.5, 4)])`;
  - vertex chamfer: `VertexChamfer`, `part.chamfer_vertices`.
- **Draft:** parting-line draft, `PartingLineDraft(solid, angle_deg, parting_plane=…)`.
- **Direct edit:**
  - `MoveFace` moves planar faces of prismatic regions;
  - `DeleteFace` removes holes, pockets and bosses and heals the gap.
- **Enclose:** `Enclose(surfaces)` gives the solid region closed off by crossing or overhanging sheets.
- **Surfaces:** `FillSurface` (N-sided patch, G0/G1 to a support), `BoundarySurface`, `OffsetSurface`, `ExtendSurface`.
- **Curves:** `CompositeCurve`, `IntersectionCurve`, `IsoparametricCurve` and `ProjectedCurve`, usable as Sweep paths, Loft guides and fill boundaries.
- **Sketch:**
  - sketch "Use": `ProjectedEdges(sketch, body)`;
  - `mirror()` now also handles arcs, splines, Bézier curves, B-splines, ellipses and custom shapes.
- **STEP import:** `ImportStep(path_or_file)` reads a STEP file like `open()` does. `ImportStep.from_text(...)` and `Part.from_step(...)` are also available. The file's units are honoured.
- **Sheet metal:**
  - corner break (`SheetMetalCornerBreak`, fillet or chamfer), carried into the flat pattern;
  - form tool (`SheetMetalFormTool`): press any solid into the sheet.

**Assemblies**
- **Joint relations:** `GearRelation`, `RackPinionRelation`, `ScrewRelation`, `LinearRelation` via `assembly.add_relation(...)`. Driving one joint moves the coupled joints, and anything downstream follows.
- **Component patterns:** `assembly.linear_pattern`, `polar_pattern`, `replicate(component, onto=[anchors])`.

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
