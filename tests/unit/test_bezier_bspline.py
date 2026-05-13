"""Unit tests for Bezier + BSpline — native curves."""

import pytest

from cadbuildr.foundation.gen.models import (
    Part,
    Sketch,
    Point,
    Bezier,
    BSpline,
)


def _sketch():
    class _P(Part):
        pass
    return Sketch(_P().xy())


def test_bezier_constructs_with_minimum_two_points():
    s = _sketch()
    curve = Bezier(points=[Point(s, 0, 0), Point(s, 10, 0)])
    assert len(curve.points) == 2


def test_bezier_supports_cubic_with_two_control_points():
    s = _sketch()
    curve = Bezier(
        points=[Point(s, 0, 0), Point(s, 3, 5), Point(s, 7, 5), Point(s, 10, 0)]
    )
    assert len(curve.points) == 4
    # Endpoints are at the extremes of the chord.
    assert (curve.points[0].x.value, curve.points[0].y.value) == (0.0, 0.0)
    assert (curve.points[-1].x.value, curve.points[-1].y.value) == (10.0, 0.0)


def test_bspline_default_degree_is_3():
    s = _sketch()
    curve = BSpline(points=[Point(s, 0, 0), Point(s, 5, 10), Point(s, 10, 0)])
    # Pydantic auto-fills the default IntParameter(value=3).
    assert curve.degree.value == 3


def test_bspline_explicit_degree_is_preserved():
    s = _sketch()
    from cadbuildr.foundation.gen.models import IntParameter
    curve = BSpline(
        points=[Point(s, 0, 0), Point(s, 5, 10), Point(s, 10, 0), Point(s, 15, 5)],
        degree=IntParameter(value=4),
    )
    assert curve.degree.value == 4
