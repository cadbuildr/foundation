"""Unit tests for GridLocations."""

import pytest

from cadbuildr.foundation import GridLocations
from cadbuildr.foundation.gen.models import Part, Sketch


def _origin():
    class _P(Part):
        pass

    p = _P()
    return Sketch(p.xy()).origin


def test_grid_locations_3x3_centered_on_anchor():
    grid = GridLocations(_origin(), x_pitch=10, y_pitch=10, n_x=3, n_y=3)
    pts = grid.positions()
    assert len(pts) == 9
    coords = sorted((p.x.value, p.y.value) for p in pts)
    expected = sorted((x * 10.0, y * 10.0) for x in (-1, 0, 1) for y in (-1, 0, 1))
    assert coords == expected


def test_grid_locations_2x4_with_distinct_pitches():
    grid = GridLocations(_origin(), x_pitch=5, y_pitch=2, n_x=2, n_y=4)
    pts = grid.positions()
    assert len(pts) == 8
    xs = sorted({p.x.value for p in pts})
    ys = sorted({p.y.value for p in pts})
    assert xs == [-2.5, 2.5]
    # Centered: y0 = -3*2/2 = -3; ys = [-3, -1, 1, 3].
    assert ys == [-3.0, -1.0, 1.0, 3.0]


def test_grid_locations_validates_counts():
    with pytest.raises(ValueError, match="n_x >= 1"):
        GridLocations(_origin(), 1, 1, 0, 1)
    with pytest.raises(ValueError, match="n_y >= 1"):
        GridLocations(_origin(), 1, 1, 1, 0)
