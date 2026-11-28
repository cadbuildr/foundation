"""CompactPolygon / CompactPolyline (with true arcs), ring(), hole_pattern()."""

import math

import pytest

from cadbuildr.foundation import (
    Arc,
    CompactPolygon,
    CompactPolyline,
    CompactProfileError,
    CustomClosedShape,
    CustomOpenShape,
    Extrusion,
    GridLocations,
    Hole,
    LinearPattern,
    Line,
    Locations,
    Part,
    Polygon,
    Sketch,
    bulge_from_sweep,
    hole_pattern,
    ring,
)
from cadbuildr.foundation.constants import DEFAULT_VALID_TYPES
from cadbuildr.foundation.dag_utils import show_dag

COMPACT_NATIVE = [*DEFAULT_VALID_TYPES, "CompactPolygon", "CompactPolyline"]


def rack_outline(module, teeth, height, backlash=0.05):
    """Same outline as stdlib's GearRack (straight 20° flanks)."""
    p = math.pi * module
    tan_a = math.tan(math.radians(20))
    half_t = (math.pi / 2 - backlash) * module / 2
    add, ded = 1.0 * module, 1.25 * module
    x0 = -teeth * p / 2
    pts = [(x0, -height), (x0, -ded)]
    for k in range(teeth):
        c = x0 + (k + 0.5) * p
        pts += [
            (c - half_t - ded * tan_a, -ded),
            (c - half_t + add * tan_a, add),
            (c + half_t - add * tan_a, add),
            (c + half_t + ded * tan_a, -ded),
        ]
    pts += [(-x0, -ded), (-x0, -height)]
    return pts


def _types(dag):
    inv = {v: k for k, v in dag["serializableNodes"].items()}
    return [inv[n["type"]] for n in dag["DAG"].values()]


def _rack(shape_cls):
    part = Part()
    s = Sketch(part.xy())
    part.add_operation(
        Extrusion(shape_cls.from_points(s, rack_outline(1, 100, 8.0)), 6)
    )
    return part


def test_rack_100_teeth_node_counts():
    before = show_dag(_rack(Polygon))
    lowered = show_dag(_rack(CompactPolygon))
    native = show_dag(_rack(CompactPolygon), valid_types=COMPACT_NATIVE)
    n_before, n_lowered, n_native = (len(d["DAG"]) for d in (before, lowered, native))
    # 404 vertices: one Point + Line per vertex (+ deduplicated floats).
    assert n_before > 1200
    # Default serialization lowers to Lines on shared Points: same geometry,
    # same size, every kernel keeps working.
    assert n_lowered <= n_before + 2
    assert _types(lowered).count("Line") == 404
    # Once a kernel reads CompactPolygon natively the outline is ONE node.
    assert _types(native).count("CompactPolygon") == 1
    assert "Line" not in _types(native)
    assert n_native < 25


def test_lowered_polygon_matches_polygon_from_points():
    pts = rack_outline(1, 4, 8.0)
    s = Sketch(Part().xy())
    prims = CompactPolygon.from_points(s, pts).expand().primitives
    assert all(isinstance(p, Line) for p in prims)
    got = [(p.p1.x.value, p.p1.y.value) for p in prims]
    assert got == pytest.approx(pts)
    assert prims[-1].p2 is prims[0].p1  # closed, shared vertex


def test_true_arc_edges_from_bulges():
    # 20 x 10 slot-like plate: right edge is a CCW semicircle bulging outward.
    s = Sketch(Part().xy())
    shape = CompactPolygon.from_points(s, [(0, 0), (20, 0, 1.0), (20, 10), (0, 10)])
    assert shape.bulges == [0.0, 1.0, 0.0, 0.0]
    out = shape.expand()
    assert isinstance(out, CustomClosedShape)
    kinds = [type(p).__name__ for p in out.primitives]
    assert kinds == ["Line", "Arc", "Line", "Line"]
    arc = out.primitives[1]
    # Semicircle from (20, 0) to (20, 10), counter-clockwise: apex at (25, 5).
    assert (arc.p2.x.value, arc.p2.y.value) == pytest.approx((25.0, 5.0))
    assert arc.p1 is out.primitives[0].p2 and arc.p3 is out.primitives[2].p1


def test_negative_bulge_and_sweep_helper():
    s = Sketch(Part().xy())
    b = bulge_from_sweep(-90.0)
    assert b == pytest.approx(-math.tan(math.pi / 8))
    line = CompactPolyline.from_points(s, [(10, 0, b), (0, 10)])
    arc = line.expand().primitives[0]
    assert isinstance(arc, Arc)
    # Clockwise quarter arc from (10,0) to (0,10) about (10,10): its midpoint
    # lies on that circle, on the side toward the origin.
    mx, my = arc.p2.x.value, arc.p2.y.value
    assert math.hypot(mx - 10, my - 10) == pytest.approx(10.0)
    assert mx < 5 and my < 5


def test_polyline_open_and_native_params():
    part = Part()
    s = Sketch(part.xy())
    shape = CompactPolyline.from_points(s, [(0, 0), (10, 0), (10, 5, 0.3), (20, 5)])
    assert isinstance(shape.expand(), CustomOpenShape)
    assert len(shape.expand().primitives) == 3
    assert shape.coords == [0, 0, 10, 0, 10, 5, 20, 5]
    assert shape.bulges == [0.0, 0.0, 0.3]


@pytest.mark.parametrize(
    "pts, match",
    [
        ([(0, 0), (1, 0)], "at least 3"),
        ([(0, 0), (1, 0), (1, 0), (0, 1)], "zero length"),
        ([(0, 0, 1, 2)], r"\(x, y\) or \(x, y, bulge\)"),
    ],
)
def test_compact_polygon_errors(pts, match):
    s = Sketch(Part().xy())
    with pytest.raises(CompactProfileError, match=match):
        CompactPolygon.from_points(s, pts)


def test_compact_coords_validation():
    s = Sketch(Part().xy())
    with pytest.raises(CompactProfileError, match="odd"):
        CompactPolygon(sketch=s, coords=[0, 0, 1, 0, 1]).compute("primitives")
    with pytest.raises(CompactProfileError, match="one value per edge"):
        CompactPolygon(sketch=s, coords=[0, 0, 1, 0, 1, 1], bulges=[0.1]).compute(
            "primitives"
        )


def test_ring_is_one_thin_wall_extrusion():
    part = Part()
    s = Sketch(part.xy())
    groove = ring(s.origin, 20, 16, -2, cut=True)
    assert isinstance(groove, Extrusion)
    assert groove.thin_wall.value == pytest.approx(4.0)
    assert groove.cut.value is True
    assert groove.shape[0].radius.value == pytest.approx(20)
    with pytest.raises(CompactProfileError):
        ring(s.origin, 10, 12, 3)


def test_hole_grid_is_one_linear_pattern():
    # goBILDA-style 29 x 53 grid, 8 mm pitch.
    def plate(holes):
        part = Part()
        s = Sketch(part.xy())
        part.add_operation(
            Extrusion(
                Polygon.from_points(
                    s, [(-120, -216), (120, -216), (120, 216), (-120, 216)]
                ),
                4,
            )
        )
        grid = GridLocations(s.origin, 8, 8, 29, 53)
        if holes == "each":
            for p in grid.positions():
                part.add_operation(Hole(p, 2.0, 4))
        else:
            part.add_operation(hole_pattern(grid, 2.0, 4))
        return part

    pattern = hole_pattern(
        GridLocations(Sketch(Part().xy()).origin, 8, 8, 29, 53), 2.0, 4
    )
    assert isinstance(pattern, LinearPattern)
    assert (pattern.count.value, pattern.count2.value) == (29, 53)
    assert [pattern.direction.x.value, pattern.direction2.y.value] == pytest.approx(
        [1, 1]
    )
    seed = pattern.shape
    assert seed.cut.value is True
    assert (
        seed.shape[0].center.x.value,
        seed.shape[0].center.y.value,
    ) == pytest.approx((-112, -208))

    n_each = len(show_dag(plate("each"))["DAG"])
    n_pattern = len(show_dag(plate("pattern"))["DAG"])
    assert n_each > 3000
    assert n_pattern < 60


def test_hole_list_is_one_cut():
    s = Sketch(Part().xy())
    op = hole_pattern(Locations(s.origin, [(0, 0), (10, 0), (0, 10)]), 1.5, -3)
    assert isinstance(op, Extrusion)
    assert op.cut.value is True and len(op.shape) == 3
    other = Sketch(Part().xy())
    with pytest.raises(ValueError, match="same sketch"):
        hole_pattern([s.origin, other.origin], 1, 1)
