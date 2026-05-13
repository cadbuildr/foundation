"""Unit tests for Helix2D + Spline tangents."""

import math

from cadbuildr.foundation.gen.models import (
    Helix2D,
    Part,
    Point,
    Sketch,
    Spline,
)


def _sketch():
    class _P(Part):
        pass
    return Sketch(_P().xy())


def test_helix2d_endpoints_match_archimedean_spiral():
    """Spiral starts at the center and ends at (radius_outer, 0) after
    n_turns full rotations."""
    s = _sketch()
    spline = Helix2D(s.origin, pitch=2, radius_outer=10, n_turns=5).expand()
    assert isinstance(spline, Spline)
    pts = spline.points
    # First sample at θ=0: r=0 → at the center.
    assert math.isclose(pts[0].x.value, 0, abs_tol=1e-9)
    assert math.isclose(pts[0].y.value, 0, abs_tol=1e-9)
    # Last sample at θ=n_turns·2π: cos(2π·n)=1, sin=0 → x=radius_outer.
    assert math.isclose(pts[-1].x.value, 10, abs_tol=1e-6)
    assert math.isclose(pts[-1].y.value, 0, abs_tol=1e-6)


def test_helix2d_sample_density_scales_with_turns():
    s = _sketch()
    short = Helix2D(s.origin, pitch=1, radius_outer=2, n_turns=2).expand()
    long = Helix2D(s.origin, pitch=1, radius_outer=8, n_turns=8).expand()
    # Longer spiral has more samples (capped at 512+1).
    assert len(long.points) > len(short.points)


def test_spline_accepts_optional_tangents():
    """: Spline now has optional start_tangent / end_tangent."""
    s = _sketch()
    spline = Spline(
        points=[Point(s, 0, 0), Point(s, 5, 5), Point(s, 10, 0)],
        start_tangent=Point(s, 1, 0),
        end_tangent=Point(s, 1, 0),
    )
    assert spline.start_tangent is not None
    assert spline.end_tangent is not None
    # Existing API still works without tangents.
    bare = Spline(points=[Point(s, 0, 0), Point(s, 1, 1)])
    assert bare.start_tangent is None
    assert bare.end_tangent is None
