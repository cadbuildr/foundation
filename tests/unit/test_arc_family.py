"""Unit tests for the explicit Arc family.

Ships ThreePointArc, RadiusArc, CenterArc, SagittaArc, TangentArc,
JernArc, EllipticalCenterArc."""

import math

from cadbuildr.foundation.gen.models import (
    Arc,
    ArcFromTwoPointsAndRadius,
    Part,
    Point,
    Sketch,
    ThreePointArc,
    RadiusArc,
    CenterArc,
    SagittaArc,
    TangentArc,
    JernArc,
)
from cadbuildr.foundation.gen.models import FloatParameter


def _sketch():
    class _P(Part):
        pass
    return Sketch(_P().xy())


def test_three_point_arc_is_alias_of_arc():
    s = _sketch()
    p1, p2, p3 = Point(s, 0, 0), Point(s, 5, 5), Point(s, 10, 0)
    arc = ThreePointArc(p1, p2, p3).expand()
    assert isinstance(arc, Arc)
    assert (arc.p1.x.value, arc.p1.y.value) == (0, 0)
    assert (arc.p2.x.value, arc.p2.y.value) == (5, 5)
    assert (arc.p3.x.value, arc.p3.y.value) == (10, 0)


def test_radius_arc_routes_through_arc_from_two_points_and_radius():
    s = _sketch()
    arc_constructor = RadiusArc(Point(s, 0, 0), Point(s, 10, 0), radius=8.0).expand()
    assert isinstance(arc_constructor, ArcFromTwoPointsAndRadius)


def test_center_arc_quarter_circle_at_origin():
    """CenterArc((0,0), R=5, 0°→90°) → p1=(5,0), p3=(0,5), p2 on the bisector."""
    s = _sketch()
    arc = CenterArc(s.origin, radius=5, start_angle_deg=0, end_angle_deg=90).expand()
    assert math.isclose(arc.p1.x.value, 5.0, abs_tol=1e-9)
    assert math.isclose(arc.p1.y.value, 0.0, abs_tol=1e-9)
    assert math.isclose(arc.p3.x.value, 0.0, abs_tol=1e-9)
    assert math.isclose(arc.p3.y.value, 5.0, abs_tol=1e-9)
    # Mid at 45°.
    assert math.isclose(arc.p2.x.value, 5 * math.cos(math.radians(45)), abs_tol=1e-9)
    assert math.isclose(arc.p2.y.value, 5 * math.sin(math.radians(45)), abs_tol=1e-9)


def test_sagitta_arc_apex_above_chord_midpoint():
    """SagittaArc((0,0)→(10,0), sagitta=2) → apex at (5, 2)."""
    s = _sketch()
    arc = SagittaArc(Point(s, 0, 0), Point(s, 10, 0), sagitta=2.0).expand()
    assert math.isclose(arc.p2.x.value, 5.0, abs_tol=1e-9)
    assert math.isclose(arc.p2.y.value, 2.0, abs_tol=1e-9)


def test_tangent_arc_vertical_tangent_makes_semicircle():
    """TangentArc(p1=(0,0), p3=(10,0), tangent=(0,1)) is a half-disk arc.

    The tangent points 90° from the chord, so the arc is a semicircle
    bulging upward; midpoint at (5, 5)."""
    s = _sketch()
    p1 = Point(s, 0, 0)
    p3 = Point(s, 10, 0)
    tangent = Point(s, 0, 1)
    arc = TangentArc(p1=p1, p3=p3, tangent=tangent).expand()
    assert isinstance(arc, Arc)
    assert math.isclose(arc.p2.x.value, 5.0, abs_tol=1e-9)
    assert math.isclose(arc.p2.y.value, 5.0, abs_tol=1e-9)


def test_tangent_arc_chord_collinear_tangent_falls_back_to_chord_midpoint():
    """Degenerate input — tangent collinear with chord — produces a 'flat'
    arc whose midpoint equals the chord midpoint."""
    s = _sketch()
    arc = TangentArc(
        p1=Point(s, 0, 0), p3=Point(s, 10, 0), tangent=Point(s, 1, 0),
    ).expand()
    assert math.isclose(arc.p2.x.value, 5.0, abs_tol=1e-9)
    assert math.isclose(arc.p2.y.value, 0.0, abs_tol=1e-9)


def test_jern_arc_180deg_sweep_with_x_tangent_lands_on_y_axis():
    """JernArc(start=(0,0), tangent=(1,0), r=5, 180°) sweeps a half-circle
    around the center (0, 5); end point at (0, 10), midpoint at (5, 5)."""
    s = _sketch()
    start = Point(s, 0, 0)
    tangent = Point(s, 1, 0)
    arc = JernArc(
        start=start, tangent=tangent,
        radius=FloatParameter(value=5.0),
        arc_size_deg=FloatParameter(value=180.0),
    ).expand()
    assert math.isclose(arc.p3.x.value, 0.0, abs_tol=1e-9)
    assert math.isclose(arc.p3.y.value, 10.0, abs_tol=1e-9)
    assert math.isclose(arc.p2.x.value, 5.0, abs_tol=1e-9)
    assert math.isclose(arc.p2.y.value, 5.0, abs_tol=1e-9)


def test_jern_arc_quarter_sweep():
    """JernArc(start=(0,0), tangent=(1,0), r=5, 90°) ends at (5, 5)."""
    s = _sketch()
    arc = JernArc(
        start=Point(s, 0, 0), tangent=Point(s, 1, 0),
        radius=FloatParameter(value=5.0),
        arc_size_deg=FloatParameter(value=90.0),
    ).expand()
    assert math.isclose(arc.p3.x.value, 5.0, abs_tol=1e-9)
    assert math.isclose(arc.p3.y.value, 5.0, abs_tol=1e-9)
