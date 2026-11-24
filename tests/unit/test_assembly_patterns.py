"""Assembly linear_pattern / polar_pattern / replicate of component instances."""

import math

import pytest

from cadbuildr.foundation import make_anchor
from cadbuildr.foundation.compute_functions import component_frames
from cadbuildr.foundation.dag_utils import show_dag
from cadbuildr.foundation.gen.models import (
    Assembly,
    BoolParameter,
    Circle,
    Extrusion,
    Part,
    RevoluteJoint,
    RigidJoint,
    Sketch,
)
from cadbuildr.foundation.math_utils import (
    quaternion_rotate_vector,
    tf_relative_to_frame,
)

NO_FLIP = BoolParameter(value=False)


def _pin(radius=1.0, length=6.0):
    part = Part()
    sketch = Sketch(part.xy())
    part.add_operation(Extrusion(Circle(sketch.origin, radius), length))
    part.add_anchor(make_anchor("foot", (0.0, 0.0, 0.0)))
    part.add_anchor(make_anchor("tip", (0.0, 0.0, length)))
    return part


def _plate():
    part = Part()
    sketch = Sketch(part.xy())
    part.add_operation(Extrusion(Circle(sketch.origin, 50.0), 4.0))
    part.add_anchor(make_anchor("hub", (0.0, 0.0, 4.0)))
    return part


def _world(anchor, assembly):
    return tf_relative_to_frame(anchor.frame, component_frames(assembly))


def _pos(anchor, assembly):
    return [round(v, 9) + 0.0 for v in _world(anchor, assembly)[0]]


# --------------------------------------------------------------------------- #
# Components placed with add_component
# --------------------------------------------------------------------------- #


def test_linear_pattern_of_an_added_component():
    asm = Assembly()
    pin = _pin()
    asm.add_component(pin, at=(5.0, 0.0, 0.0))
    pins = asm.linear_pattern(pin, [1.0, 0.0, 0.0], 4, 10.0)
    assert len(pins) == 4 and pins[0] is pin
    assert len({id(p) for p in pins}) == 4
    assert len(asm.components) == 4
    assert [_pos(p.anchor("tip"), asm) for p in pins] == [
        [5.0, 0.0, 6.0],
        [15.0, 0.0, 6.0],
        [25.0, 0.0, 6.0],
        [35.0, 0.0, 6.0],
    ]


def test_direction_is_normalised():
    asm = Assembly()
    pin = _pin()
    asm.add_component(pin)
    pins = asm.linear_pattern(pin, [0.0, 3.0, 4.0], 2, 10.0)
    assert _pos(pins[1].anchor("foot"), asm) == [0.0, 6.0, 8.0]


def test_copies_are_independent_instances():
    asm = Assembly()
    pin = _pin()
    asm.add_component(pin)
    copy = asm.linear_pattern(pin, [1.0, 0.0, 0.0], 2, 10.0)[1]
    assert copy.operations is not pin.operations
    assert copy.frame is not pin.frame
    pin.add_operation(Extrusion(Circle(Sketch(pin.xy()).origin, 3.0), 1.0))
    assert len(copy.operations) == 1  # the original's later edit stays its own


def test_polar_pattern_of_an_added_component():
    asm = Assembly()
    pin = _pin()
    asm.add_component(pin, at=(20.0, 0.0, 0.0))
    pins = asm.polar_pattern(pin, 4)
    assert [_pos(p.anchor("foot"), asm) for p in pins] == [
        [20.0, 0.0, 0.0],
        [0.0, 20.0, 0.0],
        [-20.0, 0.0, 0.0],
        [0.0, -20.0, 0.0],
    ]
    # Instances turn with the pattern: the second one's +X points along +Y.
    _, q = _world(pins[1].anchor("foot"), asm)
    assert quaternion_rotate_vector(q, [1, 0, 0]) == pytest.approx([0, 1, 0], abs=1e-9)


def test_partial_polar_span_hits_both_ends_about_an_off_origin_center():
    asm = Assembly()
    pin = _pin()
    asm.add_component(pin, at=(20.0, 10.0, 0.0))
    pins = asm.polar_pattern(pin, 3, angle_deg=180.0, center=(10.0, 10.0, 0.0))
    assert [_pos(p.anchor("foot"), asm) for p in pins] == [
        [20.0, 10.0, 0.0],
        [10.0, 20.0, 0.0],
        [0.0, 10.0, 0.0],
    ]


def test_polar_pattern_about_an_anchor():
    asm = Assembly()
    asm.add_anchor(make_anchor("axle", (100.0, 0.0, 0.0), z_axis=(1, 0, 0)))
    pin = _pin()
    asm.add_component(pin, at=(100.0, 10.0, 0.0))
    pins = asm.polar_pattern(pin, 4, about=asm.anchor("axle"))  # axis = world +X
    assert _pos(pins[1].anchor("foot"), asm) == [100.0, 0.0, 10.0]


def test_pattern_of_a_subassembly():
    sub = Assembly()
    pin = _pin()
    sub.add_component(pin, at=(0.0, 0.0, 2.0))
    sub.add_anchor(make_anchor("mark", (1.0, 0.0, 0.0)))
    top = Assembly()
    top.add_component(sub, at=(10.0, 0.0, 0.0))
    subs = top.linear_pattern(sub, [0.0, 1.0, 0.0], 3, 20.0)
    assert len(top.components) == 3
    for i, s in enumerate(subs):
        assert _pos(s.anchor("mark"), top) == [11.0, 20.0 * i, 0.0]
    inner = subs[2].components[0]
    tip = next(a for a in inner.anchors if a.name.value == "tip")
    assert _pos(tip, top) == [10.0, 40.0, 8.0]


# --------------------------------------------------------------------------- #
# Jointed components
# --------------------------------------------------------------------------- #


def _arm_with_pin():
    """A plate, an arm on a revolute hinge at its hub, a pin rigid on the arm."""
    asm = Assembly()
    plate = _plate()
    asm.add_component(plate)
    arm = Part()
    sketch = Sketch(arm.xy())
    arm.add_operation(Extrusion(Circle(sketch.origin, 3.0), 2.0))
    arm.add_anchor(make_anchor("pivot", (0.0, 0.0, 0.0)))
    arm.add_anchor(make_anchor("seat", (10.0, 0.0, 2.0)))
    hinge = RevoluteJoint(
        parent_anchor=plate.anchor("hub"),
        child_anchor=arm.anchor("pivot"),
        flip=NO_FLIP,
    )
    asm.add_joint(hinge)
    pin = _pin()
    asm.add_joint(
        RigidJoint(
            parent_anchor=arm.anchor("seat"),
            child_anchor=pin.anchor("foot"),
            flip=NO_FLIP,
        )
    )
    return asm, hinge, pin


def test_jointed_copies_get_the_same_joint_and_follow_the_parent():
    asm, hinge, pin = _arm_with_pin()
    pins = asm.linear_pattern(pin, [1.0, 0.0, 0.0], 3, 5.0)
    assert len(asm.joints) == 4  # hinge + 3 pin joints
    assert all(type(j).__name__ == "RigidJoint" for j in asm.joints[1:])
    assert [_pos(p.anchor("foot"), asm) for p in pins] == [
        [10.0, 0.0, 6.0],
        [15.0, 0.0, 6.0],
        [20.0, 0.0, 6.0],
    ]
    hinge.set_angle(math.pi / 2)  # the arm turns: every copy goes with it
    assert [_pos(p.anchor("foot"), asm) for p in pins] == [
        [0.0, 10.0, 6.0],
        [0.0, 15.0, 6.0],
        [0.0, 20.0, 6.0],
    ]


def test_jointed_copy_keeps_joint_values():
    asm = Assembly()
    plate = _plate()
    asm.add_component(plate)
    asm.add_anchor(make_anchor("axle", (30.0, 0.0, 0.0)))
    wheel = _pin(radius=5.0, length=2.0)
    wheel.add_anchor(make_anchor("rim", (5.0, 0.0, 0.0)))
    spin = RevoluteJoint(
        parent_anchor=asm.anchor("axle"),
        child_anchor=wheel.anchor("foot"),
        flip=NO_FLIP,
        angle=math.pi / 2,
    )
    asm.add_joint(spin)
    wheels = asm.polar_pattern(wheel, 2)  # second wheel at (-30, 0)
    copy_joint = asm.joints[-1]
    assert type(copy_joint).__name__ == "RevoluteJoint"
    assert copy_joint.angle.value == pytest.approx(math.pi / 2)
    # rim at +90° of the wheel, wheel turned 180° by the pattern
    assert _pos(wheels[1].anchor("rim"), asm) == pytest.approx([-30.0, -5.0, 0.0])
    copy_joint.set_angle(0.0)
    assert _pos(wheels[1].anchor("rim"), asm) == pytest.approx([-35.0, 0.0, 0.0])


# --------------------------------------------------------------------------- #
# Replicate
# --------------------------------------------------------------------------- #


def test_replicate_an_unplaced_component_onto_a_bolt_circle():
    asm = Assembly()
    plate = _plate()
    asm.add_component(plate)
    holes = plate.anchor("hub").polar_pattern(6, radius=38.0)
    pin = _pin()
    pins = asm.replicate(pin, onto=holes, child_anchor="foot", flip=False)
    assert len(pins) == 6 and pins[0] is pin
    assert len(asm.joints) == 6
    for i, p in enumerate(pins):
        a = math.radians(60 * i)
        assert _pos(p.anchor("tip"), asm) == pytest.approx(
            [38 * math.cos(a), 38 * math.sin(a), 10.0], abs=1e-9
        )


def test_replicate_a_jointed_component_skips_its_own_anchor():
    asm = Assembly()
    plate = _plate()
    asm.add_component(plate)
    holes = plate.anchor("hub").polar_pattern(4, radius=20.0)
    pin = _pin()
    asm.add_joint(
        RevoluteJoint(
            parent_anchor=holes[0],
            child_anchor=pin.anchor("foot"),
            flip=NO_FLIP,
            angle=0.3,
        )
    )
    pins = asm.replicate(pin, onto=holes)
    assert len(pins) == 4
    assert [type(j).__name__ for j in asm.joints] == ["RevoluteJoint"] * 4
    assert all(j.angle.value == pytest.approx(0.3) for j in asm.joints)
    assert _pos(pins[2].anchor("tip"), asm) == pytest.approx(
        [-20.0, 0.0, 10.0], abs=1e-9
    )


# --------------------------------------------------------------------------- #
# Errors + serialization
# --------------------------------------------------------------------------- #


def test_pattern_needs_a_placed_component():
    with pytest.raises(ValueError, match="place .* in this assembly first"):
        Assembly().linear_pattern(_pin(), [1.0, 0.0, 0.0], 3, 5.0)


def test_bad_count_raises():
    asm = Assembly()
    pin = _pin()
    asm.add_component(pin)
    with pytest.raises(ValueError, match="positive integer"):
        asm.polar_pattern(pin, 0)


def test_replicate_errors():
    asm = Assembly()
    plate = _plate()
    asm.add_component(plate)
    with pytest.raises(ValueError, match="pass child_anchor"):
        asm.replicate(_pin(), onto=[plate.anchor("hub")])
    with pytest.raises(ValueError, match="placed with add_component"):
        asm.replicate(plate, onto=[plate.anchor("hub")])
    with pytest.raises(ValueError, match="onto is empty"):
        asm.replicate(_pin(), onto=[], child_anchor="foot")


def test_patterned_assembly_serializes_every_instance():
    asm, _, pin = _arm_with_pin()
    asm.linear_pattern(pin, [1.0, 0.0, 0.0], 3, 5.0)
    dag = show_dag(asm)
    part_type = dag["serializableNodes"]["PartRoot"]
    assert sum(1 for n in dag["DAG"].values() if n["type"] == part_type) == 5
    assert show_dag(asm) == dag
