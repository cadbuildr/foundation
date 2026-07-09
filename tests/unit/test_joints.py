"""Tests for anchor-to-anchor joint placement (deterministic, no solver)."""

import math

import pytest

from cadbuildr.foundation.gen.models import (
    Anchor,
    Assembly,
    BoolParameter,
    BallJoint,
    CylindricalJoint,
    Extrusion,
    FloatParameter,
    Frame,
    JointLimits,
    Part,
    PinSlotJoint,
    PlanarJoint,
    RevoluteJoint,
    RigidJoint,
    ScrewJoint,
    Sketch,
    SliderJoint,
    Square,
    StringParameter,
)
from cadbuildr.foundation.math_utils import (
    quaternion_rotate_vector,
    tf_relative_to_frame,
)

IDENTITY_Q = [1.0, 0.0, 0.0, 0.0]


def _make_box(size=10.0):
    part = Part()
    sketch = Sketch(part.xy())
    square = Square.from_center_and_side(sketch.origin, size)
    part.add_operation(Extrusion(square, size))
    return part


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


def _boxes_with_top_bottom(size=10.0):
    """Two boxes with a +Z 'top' anchor at z=size and a -Z 'bottom' anchor
    at the origin (outward normal convention)."""
    flip_q = [0.0, 1.0, 0.0, 0.0]  # 180° about X: +Z becomes -Z
    base, child = _make_box(size), _make_box(size)
    for box in (base, child):
        box.add_anchor(_anchor("top", [0, 0, size]))
        box.add_anchor(_anchor("bottom", [0, 0, 0], flip_q))
    return base, child


def _child_root_tf(assembly, index=-1):
    root = assembly.components[index]
    return list(root.frame.position), list(root.frame.quaternion)


def _z_axis_of(q):
    return quaternion_rotate_vector(q, [0, 0, 1])


def test_rigid_joint_stacks_face_to_face():
    base, child = _boxes_with_top_bottom(10.0)
    assembly = Assembly()
    assembly.add_component(base)
    assembly.add_joint(
        RigidJoint(parent_anchor=base.anchor("top"), child_anchor=child.anchor("bottom"))
    )

    t, q = _child_root_tf(assembly)
    # bottom anchor points -Z; flip mates it against top's +Z: the child
    # sits exactly on top of the base, upright.
    assert t == pytest.approx([0, 0, 10.0])
    assert _z_axis_of(q) == pytest.approx([0, 0, 1], abs=1e-9)
    assert len(assembly.joints) == 1


def test_rigid_joint_flip_false_aligns_z():
    base, child = _boxes_with_top_bottom(10.0)
    assembly = Assembly()
    assembly.add_component(base)
    # top-to-top with flip disabled: child Z aligns with base top Z, so the
    # child hangs upside down with its own top at the base top.
    assembly.add_joint(
        RigidJoint(
            parent_anchor=base.anchor("top"),
            child_anchor=child.anchor("top"),
            flip=BoolParameter(value=False),
        )
    )
    t, q = _child_root_tf(assembly)
    assert t == pytest.approx([0, 0, 0.0])
    assert _z_axis_of(q) == pytest.approx([0, 0, 1], abs=1e-9)


def test_revolute_joint_rotates_child_about_parent_z():
    base, child = _boxes_with_top_bottom(10.0)
    child.add_anchor(_anchor("corner", [5, 0, 0]))
    assembly = Assembly()
    assembly.add_component(base)
    joint = RevoluteJoint(
        parent_anchor=base.anchor("top"),
        child_anchor=child.anchor("bottom"),
        angle=FloatParameter(value=math.pi / 2),
    )
    assembly.add_joint(joint)
    # The child rotates about the parent top axis; its corner anchor moves
    # from +X to +Y in assembly space... but mirrored by the flip: check via
    # actual anchor world position.
    t, _ = tf_relative_to_frame(child.anchor("corner").frame, assembly.frame)
    assert t[2] == pytest.approx(10.0)
    assert math.hypot(t[0], t[1]) == pytest.approx(5.0)
    assert t[0] == pytest.approx(0.0, abs=1e-9)


def test_revolute_set_angle_re_resolves_idempotently():
    base, child = _boxes_with_top_bottom(10.0)
    assembly = Assembly()
    assembly.add_component(base)
    joint = RevoluteJoint(
        parent_anchor=base.anchor("top"), child_anchor=child.anchor("bottom")
    )
    assembly.add_joint(joint)
    t0, q0 = _child_root_tf(assembly)

    joint.set_angle(math.pi / 2)
    joint.set_angle(0.0)  # back to initial: recompute must be absolute
    t1, q1 = _child_root_tf(assembly)
    assert t1 == pytest.approx(t0)
    assert q1 == pytest.approx(q0)


def test_slider_joint_offsets_along_parent_z():
    base, child = _boxes_with_top_bottom(10.0)
    assembly = Assembly()
    assembly.add_component(base)
    joint = SliderJoint(
        parent_anchor=base.anchor("top"),
        child_anchor=child.anchor("bottom"),
        offset=FloatParameter(value=4.0),
    )
    assembly.add_joint(joint)
    t, _ = _child_root_tf(assembly)
    assert t == pytest.approx([0, 0, 14.0])


def test_slider_limits_enforced_on_set_offset():
    base, child = _boxes_with_top_bottom(10.0)
    assembly = Assembly()
    assembly.add_component(base)
    joint = SliderJoint(
        parent_anchor=base.anchor("top"),
        child_anchor=child.anchor("bottom"),
        limits=JointLimits(
            min=FloatParameter(value=0.0), max=FloatParameter(value=5.0)
        ),
    )
    assembly.add_joint(joint)
    joint.set_offset(5.0)  # at the limit: fine
    with pytest.raises(ValueError, match="above limit"):
        joint.set_offset(6.0)


def test_limits_enforced_at_add_time():
    base, child = _boxes_with_top_bottom(10.0)
    assembly = Assembly()
    assembly.add_component(base)
    with pytest.raises(ValueError, match="above limit"):
        assembly.add_joint(
            RevoluteJoint(
                parent_anchor=base.anchor("top"),
                child_anchor=child.anchor("bottom"),
                angle=FloatParameter(value=1.0),
                limits=JointLimits(max=FloatParameter(value=0.5)),
            )
        )


def test_cylindrical_joint_combines_angle_and_offset():
    base, child = _boxes_with_top_bottom(10.0)
    assembly = Assembly()
    assembly.add_component(base)
    joint = CylindricalJoint(
        parent_anchor=base.anchor("top"),
        child_anchor=child.anchor("bottom"),
        angle=FloatParameter(value=math.pi),
        offset=FloatParameter(value=2.0),
    )
    assembly.add_joint(joint)
    t, _ = _child_root_tf(assembly)
    assert t == pytest.approx([0, 0, 12.0], abs=1e-9)


def test_planar_joint_slides_in_plane():
    base, child = _boxes_with_top_bottom(10.0)
    assembly = Assembly()
    assembly.add_component(base)
    assembly.add_joint(
        PlanarJoint(
            parent_anchor=base.anchor("top"),
            child_anchor=child.anchor("bottom"),
            dx=FloatParameter(value=3.0),
            dy=FloatParameter(value=-2.0),
        )
    )
    t, _ = _child_root_tf(assembly)
    assert t == pytest.approx([3.0, -2.0, 10.0])


def test_ball_joint_applies_orientation_quaternion():
    base, child = _boxes_with_top_bottom(10.0)
    assembly = Assembly()
    assembly.add_component(base)
    tilt = [math.cos(math.pi / 8), math.sin(math.pi / 8), 0.0, 0.0]  # 45° about X
    assembly.add_joint(
        BallJoint(
            parent_anchor=base.anchor("top"),
            child_anchor=child.anchor("bottom"),
            orientation=tilt,
        )
    )
    _, q = _child_root_tf(assembly)
    z = _z_axis_of(q)
    assert z == pytest.approx([0.0, -math.sqrt(2) / 2, math.sqrt(2) / 2], abs=1e-9)


def test_pin_slot_joint_slides_along_x():
    base, child = _boxes_with_top_bottom(10.0)
    assembly = Assembly()
    assembly.add_component(base)
    assembly.add_joint(
        PinSlotJoint(
            parent_anchor=base.anchor("top"),
            child_anchor=child.anchor("bottom"),
            offset=FloatParameter(value=7.0),
        )
    )
    t, _ = _child_root_tf(assembly)
    assert t == pytest.approx([7.0, 0, 10.0])


def test_screw_joint_couples_angle_to_travel():
    base, child = _boxes_with_top_bottom(10.0)
    assembly = Assembly()
    assembly.add_component(base)
    joint = ScrewJoint(
        parent_anchor=base.anchor("top"),
        child_anchor=child.anchor("bottom"),
        pitch=FloatParameter(value=1.5),
    )
    assembly.add_joint(joint)
    joint.set_angle(4.0 * math.pi)  # two full turns
    t, _ = _child_root_tf(assembly)
    assert t == pytest.approx([0, 0, 13.0])  # 10 + 2 * 1.5


def test_ground_fixes_component_at_assembly_origin():
    part = _make_box(10.0)
    part.add_anchor(_anchor("bottom", [0, 0, 0], [0.0, 1.0, 0.0, 0.0]))
    assembly = Assembly()
    assembly.ground(part.anchor("bottom"))
    t, q = _child_root_tf(assembly)
    assert t == pytest.approx([0, 0, 0])
    # Grounding uses flip=False so the part is not turned upside down; the
    # bottom anchor's -Z ends up along -Z of the assembly.
    assert len(assembly.components) == 1
    assert len(assembly.joints) == 1
    tz, _ = tf_relative_to_frame(part.anchor("bottom").frame, assembly.frame)
    assert tz == pytest.approx([0, 0, 0])


def test_parent_not_placed_raises():
    base, child = _boxes_with_top_bottom(10.0)
    assembly = Assembly()
    # base was never added to the assembly
    with pytest.raises(ValueError, match="does not chain up to"):
        assembly.add_joint(
            RigidJoint(
                parent_anchor=base.anchor("top"),
                child_anchor=child.anchor("bottom"),
            )
        )


def test_double_placement_raises():
    base, child = _boxes_with_top_bottom(10.0)
    other = _make_box(10.0)
    other.add_anchor(_anchor("top", [0, 0, 10]))
    assembly = Assembly()
    assembly.add_component(base)
    assembly.add_component(other)
    assembly.add_joint(
        RigidJoint(parent_anchor=base.anchor("top"), child_anchor=child.anchor("bottom"))
    )
    with pytest.raises(ValueError, match="already placed"):
        assembly.add_joint(
            RigidJoint(
                parent_anchor=other.anchor("top"),
                child_anchor=child.anchor("bottom"),
            )
        )


def test_joint_after_manual_add_component_raises():
    base, child = _boxes_with_top_bottom(10.0)
    assembly = Assembly()
    assembly.add_component(base)
    assembly.add_component(child)
    with pytest.raises(ValueError, match="already placed"):
        assembly.add_joint(
            RigidJoint(
                parent_anchor=base.anchor("top"),
                child_anchor=child.anchor("bottom"),
            )
        )


def test_unowned_anchor_raises():
    base, child = _boxes_with_top_bottom(10.0)
    assembly = Assembly()
    assembly.add_component(base)
    loose = _anchor("loose", [0, 0, 0])
    with pytest.raises(ValueError, match="has no owner"):
        assembly.add_joint(
            RigidJoint(parent_anchor=base.anchor("top"), child_anchor=loose)
        )


def test_chained_joints_accumulate():
    """A three-brick tower: each joint parents on the previous child."""
    size = 10.0
    b0, b1 = _boxes_with_top_bottom(size)
    _, b2 = _boxes_with_top_bottom(size)
    assembly = Assembly()
    assembly.add_component(b0)
    assembly.add_joint(
        RigidJoint(parent_anchor=b0.anchor("top"), child_anchor=b1.anchor("bottom"))
    )
    assembly.add_joint(
        RigidJoint(parent_anchor=b1.anchor("top"), child_anchor=b2.anchor("bottom"))
    )
    t, _ = _child_root_tf(assembly, index=2)
    assert t == pytest.approx([0, 0, 20.0])


def test_joint_parent_anchor_on_derived_offset():
    base, child = _boxes_with_top_bottom(10.0)
    assembly = Assembly()
    assembly.add_component(base)
    assembly.add_joint(
        RigidJoint(
            parent_anchor=base.anchor("top").offset([8.0, 16.0, 0.0], name="stud"),
            child_anchor=child.anchor("bottom"),
        )
    )
    t, _ = _child_root_tf(assembly)
    assert t == pytest.approx([8.0, 16.0, 10.0])


def test_joint_parent_inside_nested_subassembly():
    """Parent anchor on a part inside a sub-assembly placed in the outer one."""
    size = 10.0
    inner_part, child = _boxes_with_top_bottom(size)
    inner = Assembly()
    inner.add_component(inner_part)
    inner.translate([0.0, 0.0, 5.0])

    outer = Assembly()
    outer.add_component(inner)
    outer.add_joint(
        RigidJoint(
            parent_anchor=inner_part.anchor("top"),
            child_anchor=child.anchor("bottom"),
        )
    )
    t, _ = _child_root_tf(outer)
    assert t == pytest.approx([0, 0, 15.0])
