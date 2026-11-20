"""Polygon.from_points: closed polygon from 2D tuples."""

import numpy as np
import pytest

from cadbuildr.foundation.gen.models import (
    Extrusion,
    FloatParameter,
    Part,
    Point,
    Polygon,
    Sketch,
)


def _sketch():
    part = Part()
    return part, Sketch(part.xy())


def _vertices(poly):
    return [(line.p1.x.value, line.p1.y.value) for line in poly.lines]


def test_from_tuples_closes_the_loop():
    _, sketch = _sketch()
    poly = Polygon.from_points(sketch, [(0, 0), (10, 0), (10, 5), (0, 5)])
    assert isinstance(poly, Polygon)
    assert poly.sketch is sketch
    assert _vertices(poly) == [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)]
    for a, b in zip(poly.lines, poly.lines[1:] + poly.lines[:1]):
        assert a.p2 is b.p1  # edges share their vertices
    assert all(line.p1.sketch is sketch for line in poly.lines)


def test_repeated_first_point_is_not_a_zero_length_edge():
    _, sketch = _sketch()
    poly = Polygon.from_points(sketch, [(0, 0), (4, 0), (0, 3), (0, 0)])
    assert len(poly.lines) == 3


def test_accepts_lists_numpy_and_points():
    _, sketch = _sketch()
    corner = Point(
        sketch=sketch, x=FloatParameter(value=2.0), y=FloatParameter(value=2.0)
    )
    poly = Polygon.from_points(sketch, [[0, 0], np.array([2.0, 0.0]), corner])
    assert _vertices(poly) == [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0)]
    assert poly.lines[2].p1 is corner


def test_rejects_bad_input():
    _, sketch = _sketch()
    with pytest.raises(ValueError, match="at least 3"):
        Polygon.from_points(sketch, [(0, 0), (1, 0)])
    with pytest.raises(ValueError, match="2D"):
        Polygon.from_points(sketch, [(0, 0, 0), (1, 0, 0), (0, 1, 0)])
    with pytest.raises(ValueError, match="duplicate"):
        Polygon.from_points(sketch, [(0, 0), (1, 0), (1, 0), (0, 1)])
    _, other = _sketch()
    stray = Point(
        sketch=other, x=FloatParameter(value=1.0), y=FloatParameter(value=1.0)
    )
    with pytest.raises(ValueError, match="same sketch|given sketch"):
        Polygon.from_points(sketch, [(0, 0), (1, 0), stray])


def test_extrudes_and_serialises():
    part, sketch = _sketch()
    part.add_operation(
        Extrusion(Polygon.from_points(sketch, [(0, 0), (10, 0), (5, 8)]), 2.0)
    )
    poly = part.operations[0].shape[0]
    assert len(poly.lines) == 3
    assert part.to_dag()
