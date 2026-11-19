"""Passing a Plane where a Sketch is expected names the fix (issue #1090)."""

import pytest

from cadbuildr.foundation.gen.models import Part, Point, Sketch


def _plane():
    class _P(Part):
        pass

    return _P().xy()


def test_point_with_plane_names_the_fix():
    with pytest.raises(
        TypeError,
        match=r"Point needs a Sketch, not a Plane: use `Point\(Sketch\(plane\), x, y\)`",
    ):
        Point(_plane(), 1, 2)


def test_point_with_sketch_still_works():
    p = Point(Sketch(_plane()), 1, 2)
    assert p.x.value == 1
