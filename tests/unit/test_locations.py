"""Unit tests for Locations."""

import pytest

from cadbuildr.foundation import Locations
from cadbuildr.foundation.gen.models import Part, Sketch


def _origin():
    class _P(Part):
        pass
    return Sketch(_P().xy()).origin


def test_locations_emits_points_at_offsets():
    offsets = [(0, 0), (10, 0), (5, 8), (-3, -4)]
    pts = Locations(_origin(), offsets).positions()
    assert len(pts) == len(offsets)
    coords = [(p.x.value, p.y.value) for p in pts]
    assert coords == [(0.0, 0.0), (10.0, 0.0), (5.0, 8.0), (-3.0, -4.0)]


def test_locations_translates_relative_to_anchor():
    """When the anchor is shifted, every Location point shifts by the same delta."""

    class _P(Part):
        pass
    s = Sketch(_P().xy())
    from cadbuildr.foundation.gen.models import Point
    anchor = Point(s, 100, 50)
    pts = Locations(anchor, [(1, 2), (3, 4)]).positions()
    assert (pts[0].x.value, pts[0].y.value) == (101.0, 52.0)
    assert (pts[1].x.value, pts[1].y.value) == (103.0, 54.0)


def test_locations_validates_non_empty():
    with pytest.raises(ValueError, match="at least one offset"):
        Locations(_origin(), [])
