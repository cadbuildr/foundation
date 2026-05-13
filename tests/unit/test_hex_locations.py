"""Unit tests for HexLocations."""

import math

import pytest

from cadbuildr.foundation import HexLocations
from cadbuildr.foundation.gen.models import Part, Sketch


def _origin():
    class _P(Part):
        pass

    return Sketch(_P().xy()).origin


def test_hex_locations_n1_is_just_the_anchor():
    pts = HexLocations(_origin(), pitch=10, n_radial=1).positions()
    assert len(pts) == 1
    assert pts[0].x.value == 0
    assert pts[0].y.value == 0


def test_hex_locations_n2_yields_seven_points():
    """Center + 6-around at distance `pitch`."""
    pts = HexLocations(_origin(), pitch=10, n_radial=2).positions()
    assert len(pts) == 7
    # Anchor must be present.
    assert any(p.x.value == 0 and p.y.value == 0 for p in pts)
    # Every other point sits at distance `pitch`.
    radii = sorted(
        round(math.hypot(p.x.value, p.y.value), 6)
        for p in pts
        if not (p.x.value == 0 and p.y.value == 0)
    )
    assert all(r == 10.0 for r in radii)


def test_hex_locations_n3_centered_hexagonal_count():
    pts = HexLocations(_origin(), pitch=5, n_radial=3).positions()
    # 3·k² - 3·k + 1 with k=3 → 19.
    assert len(pts) == 19


def test_hex_locations_validates_n_radial():
    with pytest.raises(ValueError, match="n_radial >= 1"):
        HexLocations(_origin(), pitch=1, n_radial=0)
