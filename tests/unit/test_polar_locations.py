"""Unit tests for PolarLocations."""

import math

import pytest

from cadbuildr.foundation import PolarLocations
from cadbuildr.foundation.gen.models import Part, Sketch


def _origin():
    class _P(Part):
        pass

    return Sketch(_P().xy()).origin


def test_polar_locations_full_circle_evenly_spaced():
    pts = PolarLocations(_origin(), radius=10, count=6).positions()
    assert len(pts) == 6
    radii = [round(math.hypot(p.x.value, p.y.value), 6) for p in pts]
    assert all(r == 10.0 for r in radii)
    # Step is 60° for full-circle, no duplicate at 360°.
    angles = sorted(round(math.degrees(math.atan2(p.y.value, p.x.value)) % 360, 6) for p in pts)
    assert angles == [0.0, 60.0, 120.0, 180.0, 240.0, 300.0]


def test_polar_locations_partial_arc_includes_both_endpoints():
    pts = PolarLocations(
        _origin(), radius=5, count=3, start_angle_deg=0, angular_range_deg=90
    ).positions()
    # 90° / (3-1) = 45° step → angles 0, 45, 90.
    angles = sorted(round(math.degrees(math.atan2(p.y.value, p.x.value)), 6) for p in pts)
    assert angles == [0.0, 45.0, 90.0]


def test_polar_locations_validates_count():
    with pytest.raises(ValueError, match="count >= 1"):
        PolarLocations(_origin(), radius=1, count=0)
