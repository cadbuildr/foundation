"""Tests for Connection: one joint + geometry contributions (PartModifier)."""

import pytest

from cadbuildr.foundation import anchor_plane
from cadbuildr.foundation.dag_utils import show_dag
from cadbuildr.foundation.gen.models import (
    Anchor,
    Assembly,
    BoolParameter,
    Circle,
    Connection,
    Extrusion,
    Frame,
    Part,
    PartModifier,
    RigidJoint,
    Sketch,
    Square,
    StringParameter,
)

FLIP_Q = [0.0, 1.0, 0.0, 0.0]


def _anchor(name, position, quaternion=(1.0, 0.0, 0.0, 0.0)):
    return Anchor(
        frame=Frame(
            top_frame=None,
            name=StringParameter(value=f"anchor_{name}_frame"),
            display=BoolParameter(value=False),
            position=list(position),
            quaternion=list(quaternion),
        ),
        name=StringParameter(value=name),
    )


def _make_plate(size=30.0, thickness=5.0):
    part = Part()
    sketch = Sketch(part.xy())
    square = Square.from_center_and_side(sketch.origin, size)
    part.add_operation(Extrusion(square, thickness))
    part.add_anchor(_anchor("mount", [0, 0, thickness]))
    return part


def _make_pin(radius=2.0, length=8.0):
    part = Part()
    sketch = Sketch(part.xy())
    circle = Circle(sketch.origin, radius)
    part.add_operation(Extrusion(circle, length))
    part.add_anchor(_anchor("tip", [0, 0, 0], FLIP_Q))
    return part


def _drill_op(anchor, radius, depth):
    """A cut extrusion sketched on the anchor plane, drilling into the part."""
    sketch = Sketch(anchor_plane(anchor))
    circle = Circle(sketch.origin, radius)
    return Extrusion(circle, 0.0, start=-depth, cut=True)


def test_connection_applies_modifier_before_placement():
    plate = _make_plate()
    pin = _make_pin()
    assembly = Assembly()
    assembly.add_component(plate)

    mount = plate.anchor("mount")
    ops_before = len(plate.operations)
    assembly.add_connection(
        Connection(
            joint=RigidJoint(parent_anchor=mount, child_anchor=pin.anchor("tip")),
            modifiers=[PartModifier(anchor=mount, operations=[_drill_op(mount, 2.2, 5.0)])],
        )
    )

    # The drill landed on the plate...
    assert len(plate.operations) == ops_before + 1
    # ...and the pin got placed by the joint.
    assert len(assembly.components) == 2
    assert len(assembly.joints) == 1
    assert assembly.components[-1].frame.position == pytest.approx([0, 0, 5.0])


def test_modifier_reaches_already_converted_root():
    """Operations contributed after a part was placed must still serialize:
    pydantic copies list fields at conversion, so the root is patched too."""
    plate = _make_plate()
    pin = _make_pin()
    assembly = Assembly()
    assembly.add_component(plate)  # plate converted to PartRoot here

    mount = plate.anchor("mount")
    assembly.add_connection(
        Connection(
            joint=RigidJoint(parent_anchor=mount, child_anchor=pin.anchor("tip")),
            modifiers=[PartModifier(anchor=mount, operations=[_drill_op(mount, 2.2, 5.0)])],
        )
    )

    plate_root = assembly.components[0]
    assert len(plate_root.operations) == len(plate.operations)

    # And the DAG serializes the drill: the plate root carries two extrusions.
    dag = show_dag(assembly)
    extrusion_type = dag["serializableNodes"]["Extrusion"]
    extrusions = [n for n in dag["DAG"].values() if n["type"] == extrusion_type]
    assert len(extrusions) >= 3  # plate body + drill + pin body


def test_modifier_on_assembly_anchor_raises():
    inner = Assembly()
    inner.add_component(_make_plate())
    inner_anchor = inner.add_anchor(_anchor("frame_mount", [0, 0, 0]))

    pin = _make_pin()
    outer = Assembly()
    outer.add_component(inner)
    with pytest.raises(ValueError, match="must belong to a Part"):
        outer.add_connection(
            Connection(
                joint=RigidJoint(
                    parent_anchor=inner_anchor, child_anchor=pin.anchor("tip")
                ),
                modifiers=[
                    PartModifier(
                        anchor=inner_anchor,
                        operations=[_drill_op(inner_anchor, 2.0, 3.0)],
                    )
                ],
            )
        )


def test_connection_without_modifiers_is_just_a_joint():
    plate = _make_plate()
    pin = _make_pin()
    assembly = Assembly()
    assembly.add_component(plate)
    assembly.add_connection(
        Connection(
            joint=RigidJoint(
                parent_anchor=plate.anchor("mount"), child_anchor=pin.anchor("tip")
            )
        )
    )
    assert len(assembly.joints) == 1
    assert len(assembly.components) == 2
