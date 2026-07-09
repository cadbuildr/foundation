# Changelog

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
