"""Regression tests for the chained-`@compute` eval namespace.

The `_eval_expr` helper used to populate its eval namespace from
`vars(root)` / `root.__dict__`, which bypassed `Computable.__getattribute__`
and its lazy-compute hook. Any `@compute` whose expression referenced
another `@compute` field (e.g. `Hexagon.lines = [Line(p1=p1, ...), ...]`
where p1..p6 are themselves @compute) saw `None` for the dependent fields
and failed with a Pydantic ValidationError.

The fix builds the namespace via `getattr` over `model_fields`, so any
upstream @compute is triggered (and cached) before the downstream
expression evaluates. These tests pin that behavior."""

from cadbuildr.foundation.gen.models import (
    Hexagon,
    Part,
    Polygon,
    Sketch,
)


def test_hexagon_expand_returns_polygon_of_six_lines():
    """Hexagon's @compute(p1..p6) → @compute(lines) → @expand(Polygon) chain."""

    class _Part(Part):
        pass

    p = _Part()
    s = Sketch(p.xy())
    hexagon = Hexagon(s.origin, radius=5)
    polygon = hexagon.expand()

    assert isinstance(polygon, Polygon)
    assert len(polygon.lines) == 6
    # Each line must have real Point endpoints, not None — that was the bug.
    for line in polygon.lines:
        assert line.p1 is not None
        assert line.p2 is not None
        assert isinstance(line.p1.x.value, float)


def test_hexagon_vertices_are_inscribed_at_radius():
    """First vertex sits at angle 0 → (radius, 0); fourth at angle π → (-radius, 0)."""
    import math

    class _Part(Part):
        pass

    p = _Part()
    s = Sketch(p.xy())
    polygon = Hexagon(s.origin, radius=5).expand()

    assert polygon.lines[0].p1.x.value == 5.0
    assert polygon.lines[0].p1.y.value == 0.0
    # Fourth vertex (start of line[3]) sits at angle 2π·3/6 = π.
    assert math.isclose(polygon.lines[3].p1.x.value, -5.0, abs_tol=1e-9)
    assert math.isclose(polygon.lines[3].p1.y.value, 0.0, abs_tol=1e-9)
