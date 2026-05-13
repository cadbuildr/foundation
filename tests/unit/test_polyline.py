"""Unit tests for Polyline + FilletPolyline."""

import math

import pytest

from cadbuildr.foundation.gen.models import (
    Part,
    Sketch,
    Point,
    Polyline,
    FilletPolyline,
)


def _sketch():
    class _P(Part):
        pass

    return Sketch(_P().xy())


def test_polyline_emits_n_minus_1_lines():
    s = _sketch()
    poly = Polyline([Point(s, 0, 0), Point(s, 10, 0), Point(s, 10, 5), Point(s, 20, 5)])
    cos = poly.expand()
    # CustomOpenShape.primitives should be 3 Lines.
    assert len(cos.primitives) == 3
    # First line endpoints.
    line0 = cos.primitives[0]
    assert (line0.p1.x.value, line0.p1.y.value) == (0.0, 0.0)
    assert (line0.p2.x.value, line0.p2.y.value) == (10.0, 0.0)


def test_polyline_requires_two_points():
    s = _sketch()
    with pytest.raises(ValueError, match="at least 2 points"):
        Polyline([Point(s, 0, 0)]).expand()


def test_fillet_polyline_replaces_interior_corner_with_arc():
    """Two-segment FilletPolyline (V_0 → V_1 → V_2) gets one fillet at V_1.
    Resulting primitives: Line, Arc, Line."""
    s = _sketch()
    fp = FilletPolyline(
        [Point(s, 0, 0), Point(s, 10, 0), Point(s, 10, 10)],
        radius=2.0,
    )
    cos = fp.expand()
    types = [type(p).__name__ for p in cos.primitives]
    assert types == ["Line", "Arc", "Line"]

    # First line should end at the tangent-in point on the incoming segment.
    # For a 90° corner with R=2, tan_dist = 2/tan(45°) = 2.
    line0 = cos.primitives[0]
    assert math.isclose(line0.p2.x.value, 8.0, abs_tol=1e-9)
    assert math.isclose(line0.p2.y.value, 0.0, abs_tol=1e-9)

    # Last line should start at the tangent-out point.
    line1 = cos.primitives[2]
    assert math.isclose(line1.p1.x.value, 10.0, abs_tol=1e-9)
    assert math.isclose(line1.p1.y.value, 2.0, abs_tol=1e-9)

    # Arc midpoint sits on the bisector of the corner at the right offset.
    # 90° corner R=2: mid = V + bisector * R*(1/sin(45°) - 1)
    # bisector = (1,1)/√2, factor = 2*(√2-1) ≈ 0.828
    arc = cos.primitives[1]
    expected = (10.0 + (1 / math.sqrt(2)) * 2 * (math.sqrt(2) - 1),
                0.0 + (1 / math.sqrt(2)) * 2 * (math.sqrt(2) - 1))
    # The bisector points INTO the angle: from V=(10,0), the angle ABC has
    # arms toward (0,0) and (10,10). The bisector that lies inside the angle
    # points at (-1,1)/√2 (away from origin into the elbow). Re-derive:
    # ux,uy = b→a = (-1,0); vx,vy = b→c = (0,1). bisector = (-1,1)/√2.
    expected = (10.0 + (-1 / math.sqrt(2)) * 2 * (math.sqrt(2) - 1),
                0.0 + (1 / math.sqrt(2)) * 2 * (math.sqrt(2) - 1))
    assert math.isclose(arc.p2.x.value, expected[0], abs_tol=1e-9)
    assert math.isclose(arc.p2.y.value, expected[1], abs_tol=1e-9)


def test_fillet_polyline_rejects_too_large_radius():
    s = _sketch()
    with pytest.raises(ValueError, match="too large"):
        FilletPolyline(
            [Point(s, 0, 0), Point(s, 1, 0), Point(s, 1, 1)],
            radius=5.0,
        ).expand()
