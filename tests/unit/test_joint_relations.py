"""Joint relations: gear / rack & pinion / screw / linear couplings between
joint values (Onshape "mate relations")."""

import json
import math

import pytest

from cadbuildr.foundation import make_anchor
from cadbuildr.foundation.dag_utils import show_dag
from cadbuildr.foundation.gen.models import (
    Assembly,
    BoolParameter,
    Circle,
    CylindricalJoint,
    Extrusion,
    FloatParameter,
    GearRelation,
    JointLimits,
    LinearRelation,
    Part,
    RackPinionRelation,
    RevoluteJoint,
    RigidJoint,
    ScrewRelation,
    Sketch,
    SliderJoint,
)
from cadbuildr.foundation.math_utils import (
    quaternion_rotate_vector,
    tf_relative_to_frame,
)

NO_FLIP = BoolParameter(value=False)
TURN = 2.0 * math.pi


def _disc(radius=10.0, height=5.0):
    part = Part()
    sketch = Sketch(part.xy())
    part.add_operation(Extrusion(Circle(sketch.origin, radius), height))
    part.add_anchor(make_anchor("axis", (0.0, 0.0, 0.0)))
    part.add_anchor(make_anchor("rim", (radius, 0.0, height)))
    return part


def _frame():
    """A base plate with axle anchors at x = 0, 30, 60 and a +X slide."""
    base = Part()
    sketch = Sketch(base.xy())
    base.add_operation(Extrusion(Circle(sketch.origin, 1.0), 1.0))
    for i in range(3):
        base.add_anchor(make_anchor(f"axle_{i}", (30.0 * i, 0.0, 0.0)))
    base.add_anchor(make_anchor("slide", (0.0, -20.0, 0.0), z_axis=(1, 0, 0)))
    base.add_anchor(make_anchor("slide_2", (0.0, -40.0, 0.0), z_axis=(1, 0, 0)))
    return base


def _world(anchor, assembly):
    """(position, quaternion) of an anchor in assembly space."""
    from cadbuildr.foundation.compute_functions import component_frames

    return tf_relative_to_frame(anchor.frame, component_frames(assembly))


def _yaw(anchor, assembly):
    _, q = _world(anchor, assembly)
    x = quaternion_rotate_vector(q, [1.0, 0.0, 0.0])
    return math.atan2(x[1], x[0])


def _gear_train(n=2):
    assembly = Assembly()
    base = _frame()
    assembly.add_component(base)
    gears, joints = [], []
    for i in range(n):
        gear = _disc(radius=10.0 + 5.0 * i)
        joint = RevoluteJoint(
            parent_anchor=base.anchor(f"axle_{i}"),
            child_anchor=gear.anchor("axis"),
            flip=NO_FLIP,
        )
        assembly.add_joint(joint)
        gears.append(gear)
        joints.append(joint)
    return assembly, base, gears, joints


# --------------------------------------------------------------------------- #
# Gear
# --------------------------------------------------------------------------- #


def test_gear_driven_turns_by_ratio_and_reverse():
    assembly, _, gears, (a, b) = _gear_train()
    assembly.add_relation(GearRelation(driver=a, driven=b, ratio=0.5, reverse=True))
    a.set_angle(1.0)
    assert b.angle.value == pytest.approx(-0.5)
    assert _yaw(gears[0].anchor("rim"), assembly) == pytest.approx(1.0)
    assert _yaw(gears[1].anchor("rim"), assembly) == pytest.approx(-0.5)


def test_gear_relation_is_enforced_when_added():
    assembly, _, _, (a, b) = _gear_train()
    a.set_angle(0.6)
    assembly.add_relation(GearRelation(driver=a, driven=b, ratio=2.0, offset=0.1))
    assert b.angle.value == pytest.approx(1.3)


def test_setting_driven_back_solves_the_driver():
    assembly, _, gears, (a, b) = _gear_train()
    assembly.add_relation(GearRelation(driver=a, driven=b, ratio=0.5, reverse=True))
    b.set_angle(-0.25)
    assert a.angle.value == pytest.approx(0.5)
    assert _yaw(gears[0].anchor("rim"), assembly) == pytest.approx(0.5)


def test_gear_train_chains_and_back_solves_through_the_chain():
    assembly, _, gears, (a, b, c) = _gear_train(3)
    assembly.add_relation(GearRelation(driver=a, driven=b, ratio=2.0, reverse=True))
    assembly.add_relation(GearRelation(driver=b, driven=c, ratio=0.25, reverse=True))
    a.set_angle(0.4)
    assert b.angle.value == pytest.approx(-0.8)
    assert c.angle.value == pytest.approx(0.2)
    c.set_angle(0.5)  # c = 0.5 a  =>  a = 1.0
    assert a.angle.value == pytest.approx(1.0)
    assert b.angle.value == pytest.approx(-2.0)
    assert _yaw(gears[2].anchor("rim"), assembly) == pytest.approx(0.5)


def test_driven_gear_carries_downstream_components():
    """A pin jointed onto the driven gear follows it (through _cascade)."""
    assembly, _, gears, (a, b) = _gear_train()
    pin = _disc(radius=1.0, height=4.0)
    assembly.add_joint(
        RigidJoint(
            parent_anchor=gears[1].anchor("rim"),
            child_anchor=pin.anchor("axis"),
            flip=NO_FLIP,
        )
    )
    assembly.add_relation(GearRelation(driver=a, driven=b, ratio=1.0, reverse=True))
    a.set_angle(math.pi / 2)  # driven gear: -90° about its axle at x=30
    position, _ = _world(pin.anchor("axis"), assembly)
    r = 15.0  # second gear radius
    assert position[0] == pytest.approx(30.0)
    assert position[1] == pytest.approx(-r)


# --------------------------------------------------------------------------- #
# Rack & pinion, screw, linear
# --------------------------------------------------------------------------- #


def _pinion_and_rack(pitch_radius=10.0):
    assembly = Assembly()
    base = _frame()
    assembly.add_component(base)
    pinion = _disc(radius=pitch_radius)
    rack = _disc(radius=2.0)
    spin = RevoluteJoint(
        parent_anchor=base.anchor("axle_0"),
        child_anchor=pinion.anchor("axis"),
        flip=NO_FLIP,
    )
    slide = SliderJoint(
        parent_anchor=base.anchor("slide"),
        child_anchor=rack.anchor("axis"),
        flip=NO_FLIP,
    )
    assembly.add_joint(spin)
    assembly.add_joint(slide)
    return assembly, rack, spin, slide


def test_rack_travels_two_pi_r_per_pinion_turn():
    assembly, rack, spin, slide = _pinion_and_rack(pitch_radius=10.0)
    assembly.add_relation(
        RackPinionRelation(pinion=spin, rack=slide, pitch_radius=10.0)
    )
    spin.set_angle(TURN)
    assert slide.offset.value == pytest.approx(TURN * 10.0)
    position, _ = _world(rack.anchor("axis"), assembly)
    assert position[0] == pytest.approx(TURN * 10.0)  # slide axis is world +X
    slide.set_offset(-5.0)
    assert spin.angle.value == pytest.approx(-0.5)


def test_rack_reverse_runs_the_other_way():
    assembly, _, spin, slide = _pinion_and_rack()
    assembly.add_relation(
        RackPinionRelation(pinion=spin, rack=slide, pitch_radius=10.0, reverse=True)
    )
    spin.set_angle(1.0)
    assert slide.offset.value == pytest.approx(-10.0)


def test_screw_advances_one_pitch_per_turn():
    assembly, rack, spin, slide = _pinion_and_rack()
    assembly.add_relation(ScrewRelation(screw=spin, nut=slide, pitch=2.0))
    spin.set_angle(3 * TURN)
    assert slide.offset.value == pytest.approx(6.0)
    position, _ = _world(rack.anchor("axis"), assembly)
    assert position[0] == pytest.approx(6.0)


def test_screw_relation_on_one_cylindrical_joint():
    assembly = Assembly()
    base = _frame()
    assembly.add_component(base)
    rod = _disc(radius=2.0, height=40.0)
    lead = CylindricalJoint(
        parent_anchor=base.anchor("axle_1"),
        child_anchor=rod.anchor("axis"),
        flip=NO_FLIP,
    )
    assembly.add_joint(lead)
    assembly.add_relation(ScrewRelation(screw=lead, pitch=1.5))
    lead.set_angle(TURN)
    assert lead.offset.value == pytest.approx(1.5)
    lead.set_offset(3.0)
    assert lead.angle.value == pytest.approx(2 * TURN)
    position, _ = _world(rod.anchor("axis"), assembly)
    assert position[2] == pytest.approx(3.0)
    from cadbuildr.foundation.compute_functions import joint_set_value_method

    with pytest.raises(ValueError, match="Conflicting values"):
        joint_set_value_method(lead, angle=TURN, offset=10.0)


def test_linear_relation_couples_two_slides():
    assembly = Assembly()
    base = _frame()
    assembly.add_component(base)
    carriages = [_disc(radius=2.0) for _ in range(2)]
    slides = [
        SliderJoint(
            parent_anchor=base.anchor(name),
            child_anchor=c.anchor("axis"),
            flip=NO_FLIP,
        )
        for name, c in zip(("slide", "slide_2"), carriages)
    ]
    for s in slides:
        assembly.add_joint(s)
    assembly.add_relation(LinearRelation(driver=slides[0], driven=slides[1], ratio=2.0))
    slides[0].set_offset(7.0)
    assert slides[1].offset.value == pytest.approx(14.0)
    position, _ = _world(carriages[1].anchor("axis"), assembly)
    assert position[0] == pytest.approx(14.0)


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


def test_cycle_of_relations_raises():
    assembly, _, _, (a, b, c) = _gear_train(3)
    assembly.add_relation(GearRelation(driver=a, driven=b, ratio=1.0))
    assembly.add_relation(GearRelation(driver=b, driven=c, ratio=1.0))
    with pytest.raises(ValueError, match="cycle"):
        assembly.add_relation(GearRelation(driver=c, driven=a, ratio=1.0))
    assert len(assembly.relations) == 2


def test_dof_driven_twice_raises():
    assembly, _, _, (a, b, c) = _gear_train(3)
    assembly.add_relation(GearRelation(driver=a, driven=c, ratio=1.0))
    with pytest.raises(ValueError, match="already driven"):
        assembly.add_relation(GearRelation(driver=b, driven=c, ratio=2.0))


def test_wrong_joint_kind_raises():
    assembly, _, spin, slide = _pinion_and_rack()
    with pytest.raises(ValueError, match="needs a joint with an angle"):
        assembly.add_relation(GearRelation(driver=spin, driven=slide, ratio=1.0))
    with pytest.raises(ValueError, match="needs a joint with an offset"):
        assembly.add_relation(ScrewRelation(screw=spin, pitch=1.0))


def test_unplaced_joint_raises():
    assembly, base, _, (a, _) = _gear_train()
    loose = RevoluteJoint(
        parent_anchor=base.anchor("axle_2"),
        child_anchor=_disc().anchor("axis"),
    )
    with pytest.raises(ValueError, match="not placed yet"):
        assembly.add_relation(GearRelation(driver=a, driven=loose, ratio=1.0))


def test_non_positive_ratio_raises():
    assembly, _, _, (a, b) = _gear_train()
    with pytest.raises(ValueError, match="ratio must be > 0"):
        assembly.add_relation(GearRelation(driver=a, driven=b, ratio=-1.0))


def test_driven_limit_violation_is_atomic():
    assembly, _, gears, (a, b) = _gear_train()
    b.limits = JointLimits(
        min=FloatParameter(value=-1.0), max=FloatParameter(value=1.0)
    )
    assembly.add_relation(GearRelation(driver=a, driven=b, ratio=2.0))
    a.set_angle(0.25)
    with pytest.raises(ValueError, match="moves with this change"):
        a.set_angle(1.0)  # b would reach 2.0 > 1.0
    assert a.angle.value == pytest.approx(0.25)
    assert b.angle.value == pytest.approx(0.5)
    assert _yaw(gears[0].anchor("rim"), assembly) == pytest.approx(0.25)


def test_assembly_resolve_reenforces_relations():
    assembly, _, _, (a, b) = _gear_train()
    assembly.add_relation(GearRelation(driver=a, driven=b, ratio=3.0))
    a.angle = FloatParameter(value=0.1)  # edited by hand, no setter
    assembly.resolve()
    assert b.angle.value == pytest.approx(0.3)


# --------------------------------------------------------------------------- #
# Nesting + serialization
# --------------------------------------------------------------------------- #


def test_relation_inside_placed_subassembly_moves_with_parent_cascade():
    sub, _, gears, (a, b) = _gear_train()
    sub.add_relation(GearRelation(driver=a, driven=b, ratio=0.5, reverse=True))
    top = Assembly()
    top.add_component(sub)
    pin = _disc(radius=1.0)
    top.add_joint(
        RigidJoint(
            parent_anchor=gears[1].anchor("rim"),
            child_anchor=pin.anchor("axis"),
            flip=NO_FLIP,
        )
    )
    a.set_angle(math.pi)  # driven: -90°
    position, _ = _world(pin.anchor("axis"), top)
    assert position[0] == pytest.approx(30.0)
    assert position[1] == pytest.approx(-15.0)


def test_relations_serialize_on_the_assembly_root():
    assembly, _, _, (a, b) = _gear_train()
    assembly.add_relation(GearRelation(driver=a, driven=b, ratio=0.5, reverse=True))
    a.set_angle(0.7)
    dag = show_dag(assembly)
    root = dag["DAG"][dag["rootNodeId"]]
    relations = root["deps"]["relations"]
    assert len(relations) == 1
    node = dag["DAG"][relations[0]]
    assert node["type"] == dag["serializableNodes"]["GearRelation"]
    # The relation references the very joint nodes listed on the root.
    assert {node["deps"]["driver"], node["deps"]["driven"]} <= set(
        root["deps"]["joints"]
    )
    json.dumps(dag)
    assert show_dag(assembly) == dag  # deterministic


def test_relation_type_ids_are_appended_after_connection():
    from cadbuildr.foundation.constants import DEFAULT_TYPE_REGISTRY as reg

    assert reg["Connection"] < reg["GearRelation"] < reg["LinearRelation"]
