"""DeleteBodies / KeepBodies: explicit body selection in a multi-body part."""

import pytest

from cadbuildr.foundation import (
    DeleteBodies,
    KeepBodies,
    Part,
    Point,
    Rectangle,
    Sketch,
)
from cadbuildr.foundation.dag_utils import show_dag
from cadbuildr.foundation.interference import estimate_part_extents


def _two_blocks():
    p = Part()
    s = Sketch(p.xy())
    a = p.extrude(Rectangle.from_center_and_sides(Point(s, -10, 0), 5, 5), 5)
    b = p.extrude(Rectangle.from_center_and_sides(Point(s, 10, 0), 5, 5), 5)
    return p, a, b


def _nodes_of_type(dag, name):
    type_id = dag["serializableNodes"][name]
    return [n for n in dag["DAG"].values() if n["type"] == type_id]


def test_delete_bodies_accepts_one_op_and_adds_itself():
    p, a, b = _two_blocks()
    op = p.delete_bodies(b)
    assert isinstance(op, DeleteBodies)
    assert op.bodies == [b]
    assert p.operations[-1] is op


def test_keep_bodies_accepts_a_list():
    p, a, b = _two_blocks()
    op = p.keep_bodies([a, b])
    assert isinstance(op, KeepBodies)
    assert op.bodies == [a, b]


def test_body_selection_references_the_part_ops_in_the_dag():
    p, a, b = _two_blocks()
    p.delete_bodies(b)
    dag = show_dag(p)
    (node,) = _nodes_of_type(dag, "DeleteBodies")
    (ref,) = node["deps"]["bodies"]
    assert dag["DAG"][str(ref)]["type"] == dag["serializableNodes"]["Extrusion"]


def test_body_selection_needs_bodies():
    p, a, b = _two_blocks()
    with pytest.raises(ValueError, match="at least one body"):
        p.delete_bodies([])
    with pytest.raises(ValueError, match="before"):
        Part().keep_bodies(a)


def test_extents_ignore_body_selection():
    p, a, b = _two_blocks()
    p.delete_bodies(b)
    ext = estimate_part_extents(p)
    assert not ext.unknown
