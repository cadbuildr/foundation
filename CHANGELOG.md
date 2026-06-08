# Changelog

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
