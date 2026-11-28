"""Sketch constraints are optional intent: solved into plain coordinates at serialization."""

import json
import math
import os

import pytest

from cadbuildr.foundation import (
    Circle,
    Coincident,
    CustomClosedShape,
    Distance,
    Extrusion,
    Fix,
    Horizontal,
    HorizontalDistance,
    Line,
    Part,
    Point,
    Radius,
    Rectangle,
    Sketch,
    Vertical,
    VerticalDistance,
)
from cadbuildr.foundation.dag_utils import show_dag
from cadbuildr.foundation.sketch_solver import solve

FIXTURES = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "..", "..", "tsjs", "packages", "dag", "dag-utils", "__test__", "fixtures"
)


def _quad(s):
    a, b, c, d = Point(s, 0, 0), Point(s, 61, 2), Point(s, 59, 31), Point(s, -1, 29)
    return (a, b, c, d), (Line(a, b), Line(b, c), Line(c, d), Line(d, a))


def test_unconstrained_sketch_serializes_exactly_as_before():
    """No constraints: no solve_status, no constraints field — the DAG is unchanged."""
    p = Part()
    s = Sketch(p.xy())
    p.add_operation(Extrusion(Rectangle.from_center_and_sides(Point(s, 0, 0), 60, 30), 10))
    path = os.path.join(FIXTURES, "solids", "extrude_rect.json")
    if not os.path.exists(path):
        pytest.skip("dag-utils fixtures not available")
    with open(path) as f:
        expected = json.load(f)
    got = json.loads(json.dumps(show_dag(p)))
    assert got["DAG"] == expected["DAG"]


def test_rough_quad_is_squared_by_constraints():
    p = Part()
    s = Sketch(p.xy())
    (a, b, c, d), lines = _quad(s)
    l1, l2, l3, l4 = lines
    s.constrain([Fix(a), Horizontal(l1), Vertical(l2), Horizontal(l3), Vertical(l4), HorizontalDistance(a, b, 60), VerticalDistance(b, c, 30)])
    p.add_operation(Extrusion(CustomClosedShape(list(lines)), 10))
    dag = show_dag(p)
    sketch = next(n for n in dag["DAG"].values() if n["type"] == dag["serializableNodes"]["Sketch"])
    assert sketch["params"]["solve_status"] == "ok"
    assert (b.x.value, b.y.value) == pytest.approx((60, 0), abs=1e-9)
    assert (c.x.value, c.y.value) == pytest.approx((60, 30), abs=1e-9)
    assert (d.x.value, d.y.value) == pytest.approx((0, 30), abs=1e-9)
    # The DAG holds the solved values too, even for points the extrusion's shape
    # reaches before the Sketch node (solved on first encounter, not at the Sketch).
    float_type = dag["serializableNodes"]["FloatParameter"]
    floats = {n["params"]["value"] for n in dag["DAG"].values() if n["type"] == float_type}
    assert not floats & {61, 2, 59, 31, -1, 29}


def test_degrees_of_freedom_and_conflicts():
    s = Sketch(Part().xy())
    (a, b, c, d), (l1, l2, l3, l4) = _quad(s)
    _, _, status = solve([Horizontal(l1), Vertical(l2), Horizontal(l3), Vertical(l4)], [a, b, c, d])
    assert status == "under:4"  # position (2) + width + height
    _, _, status = solve([Distance(a, b, 10), Distance(a, b, 20)])
    assert status == "conflict"


def test_radius_dimension_and_a_shared_parameter_is_not_mutated():
    from cadbuildr.foundation import FloatParameter

    width = FloatParameter(value=4)
    s = Sketch(Part().xy())
    hole = Circle(Point(s, 0, 0), width)
    s.constrain(Radius(hole, 6))
    from cadbuildr.foundation.sketch_solver import solve_sketch

    assert solve_sketch(s) == "under:2"  # the centre is free
    assert hole.radius.value == pytest.approx(6)
    assert width.value == 4  # the shared parameter object is left alone


def test_coincident_joins_separately_drawn_lines():
    s = Sketch(Part().xy())
    l1 = Line(Point(s, 0, 0), Point(s, 40, 0))
    l2 = Line(Point(s, 41, 1), Point(s, 40, 30))
    _, x, status = solve([Fix(l1.p1), Coincident(l1.p2, l2.p1), Horizontal(l1), Vertical(l2), Distance(l1.p1, l1.p2, 40)])
    assert status.startswith(("ok", "under"))
    from cadbuildr.foundation.sketch_solver import solve_sketch

    s.constrain([Fix(l1.p1), Coincident(l1.p2, l2.p1), Horizontal(l1), Vertical(l2), Distance(l1.p1, l1.p2, 40)])
    solve_sketch(s)
    assert (l2.p1.x.value, l2.p1.y.value) == pytest.approx((40, 0), abs=1e-9)
    assert math.isclose(l2.p2.x.value, 40, abs_tol=1e-9)
