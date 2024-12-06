from cadbuildr.foundation.sketch.primitives.arc import (
    get_arc_center_from_3_points_coords,
)
import pytest


def test_arc_center():
    p1x = 1
    p1y = 1

    p2x = 2
    p2y = 4

    p3x = 5
    p3y = 3

    x0, y0 = get_arc_center_from_3_points_coords(p1x, p1y, p2x, p2y, p3x, p3y)

    assert x0 == pytest.approx(3.0)
    assert y0 == pytest.approx(2.0)
