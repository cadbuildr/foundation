"""LinearPattern grids, CurvePattern along a path, body patterns (shape=None)."""

import pytest

from cadbuildr.foundation import (
    CurvePattern,
    Extrusion,
    Helix3D,
    LinearPattern,
    Part,
    Point,
    Point3D,
    Rectangle,
    Sketch,
    Spline3D,
)
from cadbuildr.foundation.dag_utils import show_dag
from cadbuildr.foundation.interference import estimate_part_extents


def _part_and_cube():
    p = Part()
    s = Sketch(p.xy())
    cube = Extrusion(Rectangle.from_center_and_sides(Point(s, 0, 0), 2, 2), 2)
    return p, cube


def test_linear_pattern_defaults_to_one_direction():
    p, cube = _part_and_cube()
    op = p.linear_pattern(cube, [1, 0, 0], 3, 5)
    assert op.direction2 is None
    assert op.count2.value == 1
    assert op.spacing2.value == 0.0


def test_linear_pattern_grid_fields():
    p, cube = _part_and_cube()
    op = p.linear_pattern(
        cube, [1, 0, 0], 3, 5, direction2=[0, 1, 0], count2=2, spacing2=6
    )
    assert (op.direction2.x.value, op.direction2.y.value) == (0, 1)
    assert op.count2.value == 2
    assert op.spacing2.value == 6


def test_linear_pattern_count2_needs_direction2():
    p, cube = _part_and_cube()
    with pytest.raises(ValueError, match="count2 > 1 needs a direction2"):
        p.linear_pattern(cube, [1, 0, 0], 3, 5, count2=2)


def test_grid_extents_cover_both_directions():
    p, cube = _part_and_cube()
    p.linear_pattern(cube, [1, 0, 0], 3, 5, direction2=[0, 1, 0], count2=2, spacing2=6)
    ext = estimate_part_extents(p)
    assert not ext.unknown
    corners = [c for box in ext.boxes for c in box.corners()]
    assert max(c[0] for c in corners) == pytest.approx(11)
    assert max(c[1] for c in corners) == pytest.approx(7)


def test_curve_pattern_shortcut():
    p, cube = _part_and_cube()
    helix = Helix3D(40, 40, 20, Point3D(0, 0, 0), Point3D(0, 0, 1))
    op = p.curve_pattern(cube, helix, 5, align_to_path=True)
    assert isinstance(op, CurvePattern)
    assert op.align_to_path.value is True
    assert p.operations[-1] is op
    dag = show_dag(p)
    assert "CurvePattern" in dag["serializableNodes"]


def test_curve_pattern_default_is_translate_only():
    p, cube = _part_and_cube()
    op = CurvePattern(cube, Spline3D([Point3D(0, 0, 0), Point3D(30, 0, 0)]), 4)
    assert op.align_to_path.value is False


def test_body_pattern_needs_features_before_it():
    with pytest.raises(ValueError, match="add features before the pattern"):
        Part().linear_pattern(None, [1, 0, 0], 3, 5)
    p, cube = _part_and_cube()
    p.add_operation(cube)
    op = p.polar_pattern(None, 4)
    assert op.shape is None
    # A body pattern can't be bounded from the ops alone.
    assert estimate_part_extents(p).unknown


def test_old_positional_linear_pattern_still_works():
    p, cube = _part_and_cube()
    op = LinearPattern(cube, Point3D(1, 0, 0), 3, 5)
    assert op.count.value == 3 and op.count2.value == 1
