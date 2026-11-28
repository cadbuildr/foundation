"""Curves and sketch (#1208): new Path3D curves, sketch "Use" (ProjectedEdges)
and sketch mirror of every boundary element."""

import pathlib
import re

import pytest
from cadbuildr.foundation import (
    Arc,
    BSpline,
    Bezier,
    Circle,
    CompositeCurve,
    CustomClosedShape,
    CustomOpenShape,
    Ellipse,
    EllipseArc,
    Extrusion,
    IntersectionCurve,
    IsoDirection,
    IsoparametricCurve,
    Line,
    Part,
    Point,
    Point3D,
    ProjectedCurve,
    ProjectedEdges,
    Rectangle,
    Sketch,
    Spline,
    Spline3D,
    Sphere,
    Sweep,
    ExtrudedSurface,
    mirror,
)
from cadbuildr.foundation.dag_utils import show_dag

# Monorepo root (six levels up); a shallow standalone checkout has fewer
# parents, so fall back to the filesystem root, where the schema is absent.
_PARENTS = pathlib.Path(__file__).resolve().parents
SCHEMA = _PARENTS[min(6, len(_PARENTS) - 1)] / "schemas/foundation/schema.graphql"


def _xy(p):
    return (round(p.x.value, 9), round(p.y.value, 9))


def _y_axis(s):
    return Line(Point(s, 0, -1), Point(s, 0, 1))


def _types(part):
    dag = show_dag(part)
    names = {v: k for k, v in dag["serializableNodes"].items()}
    return {names[n["type"]] for n in dag["DAG"].values()}


def test_body_operation_is_solid_plus_surface_operations():
    if not SCHEMA.exists():
        pytest.skip("schema.graphql only exists in the monorepo")
    text = SCHEMA.read_text()

    def members(name):
        m = re.search(r"union %s =\s*\n((?:\s*\|?\s*\w+\s*\n)+)" % name, text)
        return {x.strip(" |") for x in m.group(1).split("\n") if x.strip(" |")}

    assert members("BodyOperation") == members("SolidOperation") | members(
        "SurfaceOperation"
    )


def test_new_curves_are_sweep_paths():
    p = Part()
    s = Sketch(p.xy())
    a = Spline3D(points=[Point3D(0, 0, 0), Point3D(0, 0, 10)])
    b = Spline3D(points=[Point3D(0, 0, 10), Point3D(0, 0, 20)])
    path = ProjectedCurve(
        CompositeCurve(curves=[a, b]), p.xz(), direction=Point3D(0, 1, 0)
    )
    p.add_operation(Sweep(Circle(s.origin, 1), path))
    assert {"CompositeCurve", "ProjectedCurve", "Sweep"} <= _types(p)


def test_intersection_and_iso_curves_serialize():
    p = Part()
    s = Sketch(p.xy())
    ball, tube = Sphere(s.origin, 20), ExtrudedSurface(Circle(s.origin, 12), 40)
    iso = IsoparametricCurve(tube, IsoDirection.V, 0.25)
    assert iso.at.value == 0.25 and iso.face_finder is None
    p.add_operation(
        Sweep(Circle(Sketch(p.xz()).origin, 1), IntersectionCurve(ball, tube))
    )
    p.add_operation(Sweep(Circle(Sketch(p.xz()).origin, 1), iso))
    assert {"IntersectionCurve", "IsoparametricCurve"} <= _types(p)


def test_projected_edges_is_a_profile_and_not_auto_registered():
    p = Part()
    box = Extrusion(Rectangle.from_center_and_sides(Sketch(p.xy()).origin, 20, 10), 5)
    up = Sketch(p.xy().get_parallel_plane(30))
    used = ProjectedEdges(up, box)
    # Not added to up.elements: that would be a cycle when the body is drawn on `up`.
    assert used not in up.elements
    p.add_operation(Extrusion(used, 3))
    assert "ProjectedEdges" in _types(p)


def test_mirror_arc_spline_bezier_bspline():
    s = Sketch(Part().xy())
    ax = _y_axis(s)
    arc = mirror(Arc(Point(s, 1, 0), Point(s, 2, 1), Point(s, 1, 2)), ax)
    assert isinstance(arc, Arc)
    assert [_xy(arc.p1), _xy(arc.p2), _xy(arc.p3)] == [(-1, 0), (-2, 1), (-1, 2)]
    sp = mirror(
        Spline([Point(s, 1, 0), Point(s, 3, 1)], start_tangent=Point(s, 1, 1)), ax
    )
    assert isinstance(sp, Spline) and [_xy(q) for q in sp.points] == [(-1, 0), (-3, 1)]
    assert _xy(sp.start_tangent) == (-1, 1)
    bz = mirror(Bezier([Point(s, 1, 0), Point(s, 2, 2), Point(s, 3, 0)]), ax)
    assert isinstance(bz, Bezier) and _xy(bz.points[1]) == (-2, 2)
    bs = mirror(BSpline([Point(s, 1, 0), Point(s, 2, 2), Point(s, 3, 0)], 2), ax)
    assert isinstance(bs, BSpline) and bs.degree.value == 2


def test_mirror_custom_shapes_keep_their_type():
    s = Sketch(Part().xy())
    a, b, c = Point(s, 1, 0), Point(s, 4, 0), Point(s, 1, 3)
    closed = CustomClosedShape([Line(a, b), Arc(b, Point(s, 3, 2.5), c), Line(c, a)])
    m = mirror(closed, _y_axis(s))
    assert isinstance(m, CustomClosedShape)
    assert [type(x).__name__ for x in m.primitives] == ["Line", "Arc", "Line"]
    assert _xy(m.primitives[0].p2) == (-4, 0)
    opened = mirror(CustomOpenShape([Line(a, b)]), _y_axis(s))
    assert isinstance(opened, CustomOpenShape)


def test_mirror_ellipses_across_axis_lines_only():
    s = Sketch(Part().xy())
    e = mirror(Ellipse(Point(s, 5, 1), 3, 1), _y_axis(s))
    assert _xy(e.center) == (-5, 1) and e.a.value == 3
    arc = mirror(
        EllipseArc(Point(s, 5, 0), 3, 1, 0.0, 1.0), Line(Point(s, 0, 2), Point(s, 1, 2))
    )
    assert _xy(arc.center) == (5, 4)
    assert arc.start_angle.value == pytest.approx(
        0.0
    ) and arc.end_angle.value == pytest.approx(-1.0)
    with pytest.raises(TypeError, match="slanted line"):
        mirror(Ellipse(Point(s, 5, 1), 3, 1), Line(Point(s, 0, 0), Point(s, 1, 1)))
