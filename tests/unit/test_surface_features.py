"""FillSurface / BoundarySurface / OffsetSurface / ExtendSurface (#1207): the
DAG carries the inputs, defaults are named, and the new sheets compose with
Thicken / Stitch."""

from cadbuildr.foundation import (
    BoundarySurface,
    Circle,
    EdgeFinder,
    ExtendSurface,
    ExtrudedSurface,
    FillSurface,
    InPlaneFinderRule,
    OffsetSurface,
    Part,
    PlanarSurface,
    Point3D,
    Rectangle,
    Sketch,
    Spline3D,
    Stitch,
    SurfaceContinuity,
    Thicken,
)
from cadbuildr.foundation.dag_utils import show_dag


def _line(a, b):
    return Spline3D(points=[Point3D(*a), Point3D(*b)])


def _square():
    c = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)]
    return [_line(c[i], c[(i + 1) % 4]) for i in range(4)]


def _nodes(part, type_name):
    dag = show_dag(part)
    idx = dag["serializableNodes"][type_name]
    return dag, [n for n in dag["DAG"].values() if n["type"] == idx]


def _type(dag, node_id):
    names = {v: k for k, v in dag["serializableNodes"].items()}
    return names[dag["DAG"][node_id]["type"]]


def test_fill_surface_defaults_to_g0_curves_only():
    fill = FillSurface(curves=_square())
    assert fill.continuity == SurfaceContinuity.G0
    assert fill.points == []
    assert fill.support is None and fill.edge_finder is None
    p = Part()
    p.add_operation(fill)
    _, [node] = _nodes(p, "FillSurface")
    assert len(node["deps"]["curves"]) == 4


def test_fill_surface_with_support_and_g1_serializes_support_and_finder():
    p = Part()
    s = Sketch(p.xy())
    tube = ExtrudedSurface(Circle(s.origin, 10), 20)
    top = EdgeFinder(InPlaneFinderRule(p.xy().get_parallel_plane(20)))
    cap = FillSurface(
        support=tube,
        edge_finder=top,
        continuity=SurfaceContinuity.G1,
        points=[Point3D(0, 0, 26)],
    )
    p.add_operation(Stitch(surfaces=[tube, cap]))
    dag, [node] = _nodes(p, "FillSurface")
    assert {"support", "edge_finder", "points"} <= set(node["deps"])
    assert node["params"]["continuity"].endswith("G1")
    assert _type(dag, node["deps"]["support"]) == "ExtrudedSurface"


def test_boundary_surface_keeps_curve_order():
    curves = _square()
    p = Part()
    p.add_operation(BoundarySurface(curves=curves))
    dag, [node] = _nodes(p, "BoundarySurface")
    assert len(node["deps"]["curves"]) == 4
    assert all(_type(dag, c) == "Spline3D" for c in node["deps"]["curves"])


def test_offset_and_extend_are_surfaces_thicken_accepts():
    p = Part()
    s = Sketch(p.xy())
    flat = PlanarSurface(Rectangle.from_center_and_sides(s.origin, 20, 10))
    sheet = ExtendSurface(OffsetSurface(flat, 3.0), 5.0)
    p.add_operation(Thicken(sheet, 1.0))
    dag, [ext] = _nodes(p, "ExtendSurface")
    _, [off] = _nodes(p, "OffsetSurface")
    assert _type(dag, ext["deps"]["surface"]) == "OffsetSurface"
    assert dag["DAG"][ext["deps"]["distance"]]["params"]["value"] == 5.0
    assert dag["DAG"][off["deps"]["distance"]]["params"]["value"] == 3.0
