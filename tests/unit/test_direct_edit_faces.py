"""MoveFace / DeleteFace (#1200): node defaults and DAG shape."""

from cadbuildr.foundation import (
    ContainsPointFinderRule,
    DeleteFace,
    Extrusion,
    FaceFinder,
    MoveFace,
    Part,
    Point,
    Point3D,
    Rectangle,
    Sketch,
)
from cadbuildr.foundation.dag_utils import show_dag


def body(p):
    s = Sketch(p.xy())
    return Extrusion([Rectangle.from_center_and_sides(Point(s, 0, 0), 40, 30)], 20)


def _nodes(dag, op):
    types = {v: k for k, v in dag["serializableNodes"].items()}
    return [n for n in dag["DAG"].values() if types[n["type"]] == op]


def top():
    return FaceFinder(ContainsPointFinderRule(Point3D(0, 0, 20)))


def test_move_face_defaults_to_no_motion():
    p = Part()
    op = MoveFace(body(p), top())
    assert (op.translation.x.value, op.translation.y.value, op.translation.z.value) == (
        0,
        0,
        0,
    )
    assert op.rotation_angle.value == 0
    assert (
        op.rotation_axis.x.value,
        op.rotation_axis.y.value,
        op.rotation_axis.z.value,
    ) == (0, 0, 1)


def test_move_face_translation_is_positional():
    p = Part()
    op = MoveFace(body(p), top(), Point3D(0, 0, 5))
    p.add_operation(op)
    assert op.translation.z.value == 5
    (node,) = _nodes(show_dag(p), "MoveFace")
    assert {
        "solid",
        "face_finder",
        "translation",
        "rotation_angle",
        "rotation_axis",
        "rotation_origin",
    } <= set(node["deps"])


def test_delete_face_node():
    p = Part()
    op = DeleteFace(body(p), top())
    p.add_operation(op)
    (node,) = _nodes(show_dag(p), "DeleteFace")
    assert set(node["deps"]) == {"solid", "face_finder"}
