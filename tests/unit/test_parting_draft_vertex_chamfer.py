"""PartingLineDraft and VertexChamfer / Part.chamfer_vertices (#1206)."""

import pytest

from cadbuildr.foundation import (
    EdgeFinder,
    Extrusion,
    InPlaneFinderRule,
    Part,
    PartingLineDraft,
    Point,
    Point3D,
    Rectangle,
    Sketch,
    VertexChamfer,
)
from cadbuildr.foundation.dag_utils import show_dag


def block():
    p = Part()
    s = Sketch(p.xy())
    ext = p.extrude(Rectangle.from_center_and_sides(Point(s, 0, 0), 40, 30), 20)
    return p, ext


def _nodes(dag, op):
    types = {v: k for k, v in dag["serializableNodes"].items()}
    return [n for n in dag["DAG"].values() if types[n["type"]] == op]


def test_chamfer_vertices_adds_a_solidless_vertex_chamfer_on_every_corner():
    p, _ = block()
    op = p.chamfer_vertices(3.0)
    assert isinstance(op, VertexChamfer) and op.solid is None and op.vertices is None
    assert p.operations[-1] is op
    (node,) = _nodes(show_dag(p), "VertexChamfer")
    assert "solid" not in node["deps"] and "vertices" not in node["deps"]


def test_chamfer_vertices_at_points():
    p, _ = block()
    op = p.chamfer_vertices(2.0, at=[(20, 15, 20), Point3D(-20, -15, 0)])
    assert [(v.x.value, v.y.value, v.z.value) for v in op.vertices] == [
        (20, 15, 20),
        (-20, -15, 0),
    ]
    (node,) = _nodes(show_dag(p), "VertexChamfer")
    assert len(node["deps"]["vertices"]) == 2


@pytest.mark.parametrize("distance", [0.0, -1.0])
def test_chamfer_vertices_distance_must_be_positive(distance):
    p, _ = block()
    with pytest.raises(ValueError, match="must be positive"):
        p.chamfer_vertices(distance)


def test_chamfer_vertices_needs_features_first():
    with pytest.raises(ValueError, match="add the features"):
        Part().chamfer_vertices(1.0)


def test_chamfer_vertices_rejects_an_empty_corner_list():
    p, _ = block()
    with pytest.raises(ValueError, match="empty"):
        p.chamfer_vertices(1.0, at=[])


def test_parting_line_draft_defaults_to_both_sides():
    p = Part()
    s = Sketch(p.xy())
    body = Extrusion([Rectangle.from_center_and_sides(Point(s, 0, 0), 40, 30)], 20)
    op = PartingLineDraft(body, 5.0, parting_plane=p.xy().get_parallel_plane(10))
    p.add_operation(op)
    assert op.both_sides.value is True
    (node,) = _nodes(show_dag(p), "PartingLineDraft")
    assert {"solid", "angle_deg", "parting_plane", "both_sides"} <= set(node["deps"])
    assert "parting_edges" not in node["deps"]


def test_parting_line_draft_about_an_edge_chain():
    p = Part()
    s = Sketch(p.xy())
    body = Extrusion([Rectangle.from_center_and_sides(Point(s, 0, 0), 40, 30)], 20)
    op = PartingLineDraft(
        body,
        4.0,
        parting_edges=EdgeFinder(InPlaneFinderRule(p.xy(), 5)),
        both_sides=False,
    )
    p.add_operation(op)
    (node,) = _nodes(show_dag(p), "PartingLineDraft")
    assert "parting_edges" in node["deps"] and "parting_plane" not in node["deps"]
    assert op.both_sides.value is False
