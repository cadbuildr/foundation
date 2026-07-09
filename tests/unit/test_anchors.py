"""Tests for Anchor (mate connector) creation, lookup, and serialization."""

import math

import pytest

from cadbuildr.foundation.gen.models import (
    Anchor,
    Assembly,
    BoolParameter,
    Extrusion,
    Frame,
    Part,
    Sketch,
    Square,
    StringParameter,
)
from cadbuildr.foundation.dag_utils import show_dag
from cadbuildr.foundation.math_utils import (
    axis_angle_to_quaternion,
    quaternion_rotate_vector,
    tf_relative_to_frame,
)


def _make_box(size=10.0):
    part = Part()
    sketch = Sketch(part.xy())
    square = Square.from_center_and_side(sketch.origin, size)
    part.add_operation(Extrusion(square, size))
    return part


def _anchor(name, position, quaternion=(1.0, 0.0, 0.0, 0.0), top_frame=None):
    return Anchor(
        frame=Frame(
            top_frame=top_frame,
            name=StringParameter(value=f"anchor_{name}_frame"),
            display=BoolParameter(value=False),
            position=list(position),
            quaternion=list(quaternion),
        ),
        name=StringParameter(value=name),
    )


def test_add_and_get_anchor():
    part = _make_box()
    added = part.add_anchor(_anchor("top", [0, 0, 10]))
    assert part.anchor("top") is added
    # Frame rooted under the part frame by add_anchor
    assert added.frame.top_frame is part.frame


def test_duplicate_anchor_name_raises():
    part = _make_box()
    part.add_anchor(_anchor("top", [0, 0, 10]))
    with pytest.raises(ValueError, match="already exists"):
        part.add_anchor(_anchor("top", [0, 0, 20]))


def test_unknown_anchor_lists_available_names():
    part = _make_box()
    part.add_anchor(_anchor("top", [0, 0, 10]))
    part.add_anchor(_anchor("bottom", [0, 0, 0]))
    with pytest.raises(ValueError) as excinfo:
        part.anchor("side")
    assert "top" in str(excinfo.value)
    assert "bottom" in str(excinfo.value)


def test_anchor_from_plane_chains_through_plane_frame():
    part = _make_box()
    plane = part.xy()
    anchor = Anchor.from_plane(plane, "face")
    assert anchor.frame.top_frame is plane.frame
    # add_anchor must keep the plane chaining (frame already rooted)
    part.add_anchor(anchor)
    assert anchor.frame.top_frame is plane.frame


def test_derived_anchor_offset_follows_base():
    part = _make_box()
    base = part.add_anchor(_anchor("top", [0, 0, 10]))
    derived = base.offset([16.0, 8.0, 0.0], name="stud_2_1")
    assert derived.frame.top_frame is base.frame
    t, _ = tf_relative_to_frame(derived.frame, part.frame)
    assert t == pytest.approx([16.0, 8.0, 10.0])
    # Derived name is prefixed with the base anchor name
    assert derived.name.value == "top_stud_2_1"


def test_derived_anchor_rotated_and_flipped():
    part = _make_box()
    base = part.add_anchor(_anchor("top", [0, 0, 10]))

    rotated = base.rotated(math.pi / 2)
    _, q = tf_relative_to_frame(rotated.frame, part.frame)
    x_axis = quaternion_rotate_vector(q, [1, 0, 0])
    assert x_axis == pytest.approx([0, 1, 0], abs=1e-9)

    flipped = base.flipped()
    _, qf = tf_relative_to_frame(flipped.frame, part.frame)
    z_axis = quaternion_rotate_vector(qf, [0, 0, 1])
    assert z_axis == pytest.approx([0, 0, -1], abs=1e-9)


def test_anchors_survive_to_dag():
    part = _make_box()
    part.add_anchor(_anchor("top", [0, 0, 10]))
    dag = show_dag(part)
    assert "Anchor" in dag["serializableNodes"]
    anchor_type = dag["serializableNodes"]["Anchor"]
    anchor_nodes = [n for n in dag["DAG"].values() if n["type"] == anchor_type]
    assert len(anchor_nodes) == 1
    root_node = dag["DAG"][dag["rootNodeId"]]
    registered = root_node.get("deps", {}).get("anchors", [])
    anchor_ids = [
        nid for nid, n in dag["DAG"].items() if n["type"] == anchor_type
    ]
    assert anchor_ids[0] in registered


def test_anchor_reparents_through_add_component():
    part = _make_box()
    anchor = part.add_anchor(_anchor("top", [0, 0, 10]))
    part.translate([5.0, 0.0, 0.0])

    assembly = Assembly()
    assembly.add_component(part)

    # After conversion the part frame chains to the assembly frame, and the
    # anchor follows: its assembly-space transform includes the translate.
    t, _ = tf_relative_to_frame(anchor.frame, assembly.frame)
    assert t == pytest.approx([5.0, 0.0, 10.0])


def test_assembly_anchor_reparents_through_nested_add_component():
    inner = Assembly()
    inner.add_component(_make_box())
    anchor = inner.add_anchor(_anchor("mount", [0, 0, 20]))
    inner.translate([0.0, 7.0, 0.0])

    outer = Assembly()
    outer.add_component(inner)

    # The inner assembly gets a fresh frame at conversion; its direct anchors
    # must be re-rooted so they keep following it.
    t, _ = tf_relative_to_frame(anchor.frame, outer.frame)
    assert t == pytest.approx([0.0, 7.0, 20.0])
