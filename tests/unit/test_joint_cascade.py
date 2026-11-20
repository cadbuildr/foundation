"""Joint re-resolution: cascades downstream, works inside placed sub-assemblies."""

import math

import pytest

from cadbuildr.foundation.gen.models import (
    Anchor,
    Assembly,
    BoolParameter,
    Extrusion,
    Frame,
    Part,
    RevoluteJoint,
    RigidJoint,
    Sketch,
    SliderJoint,
    Square,
    StringParameter,
)
from cadbuildr.foundation.math_utils import tf_relative_to_frame


def _anchor(name, position):
    return Anchor(
        frame=Frame(
            top_frame=None,
            name=StringParameter(value=f"anchor_{name}_frame"),
            display=BoolParameter(value=False),
            position=list(position),
            quaternion=[1.0, 0.0, 0.0, 0.0],
        ),
        name=StringParameter(value=name),
    )


def _link(length=100.0):
    """A bar along +X with a 'base' anchor at the origin and a 'tip' at x=length."""
    part = Part()
    sketch = Sketch(part.xy())
    part.add_operation(Extrusion(Square.from_center_and_side(sketch.origin, 5.0), 5.0))
    part.add_anchor(_anchor("base", [0.0, 0.0, 0.0]))
    part.add_anchor(_anchor("tip", [length, 0.0, 0.0]))
    return part


def _revolute(parent, child):
    # flip=False keeps the Z axes aligned, so angles are planar rotations
    # about the world +Z and positions are easy to state by hand.
    return RevoluteJoint(
        parent_anchor=parent, child_anchor=child, flip=BoolParameter(value=False)
    )


def _rigid(parent, child):
    return RigidJoint(
        parent_anchor=parent, child_anchor=child, flip=BoolParameter(value=False)
    )


def _world(anchor):
    return tf_relative_to_frame(anchor.frame)[0]


def _chain(lengths=(100.0, 100.0, 100.0)):
    a, b, c = (_link(length) for length in lengths)
    asm = Assembly()
    asm.ground(a.anchor("base"))
    j1 = _revolute(a.anchor("tip"), b.anchor("base"))
    j2 = _revolute(b.anchor("tip"), c.anchor("base"))
    asm.add_joint(j1)
    asm.add_joint(j2)
    return asm, (a, b, c), (j1, j2)


# --------------------------------------------------------------------------- #
# 1. Cascade
# --------------------------------------------------------------------------- #


def test_three_link_chain_cascades_on_set_angle():
    _, (a, b, c), (j1, _) = _chain()
    assert _world(c.anchor("base")) == pytest.approx([200.0, 0.0, 0.0])

    j1.set_angle(math.pi / 2)

    assert _world(b.anchor("base")) == pytest.approx([100.0, 0.0, 0.0])
    assert _world(b.anchor("tip")) == pytest.approx([100.0, 100.0, 0.0])
    # C follows B without re-resolving j2 by hand.
    assert _world(c.anchor("base")) == pytest.approx([100.0, 100.0, 0.0])
    assert _world(c.anchor("tip")) == pytest.approx([100.0, 200.0, 0.0])


def test_cascade_composes_both_angles():
    _, (_, _, c), (j1, j2) = _chain()
    j2.set_angle(math.pi / 2)
    j1.set_angle(math.pi / 2)  # j2's relative angle is kept
    assert _world(c.anchor("tip")) == pytest.approx([0.0, 100.0, 0.0])
    j1.set_angle(0.0)
    assert _world(c.anchor("tip")) == pytest.approx([200.0, 100.0, 0.0])


def test_rigid_child_of_moved_link_follows():
    asm, (_, b, _), (j1, _) = _chain()
    bracket = _link(10.0)
    asm.add_joint(
        _rigid(b.anchor("tip").offset([0.0, 0.0, 5.0]), bracket.anchor("base"))
    )
    assert _world(bracket.anchor("tip")) == pytest.approx([210.0, 0.0, 5.0])

    j1.set_angle(-math.pi / 2)

    assert _world(bracket.anchor("base")) == pytest.approx([100.0, -100.0, 5.0])
    assert _world(bracket.anchor("tip")) == pytest.approx([100.0, -110.0, 5.0])


def test_slider_downstream_of_revolute_follows():
    asm, (_, b, _), (j1, _) = _chain()
    carriage = _link(1.0)
    slider = SliderJoint(
        parent_anchor=b.anchor("tip").rotated(math.pi / 2, axis=(0.0, 1.0, 0.0)),
        child_anchor=carriage.anchor("base"),
        flip=BoolParameter(value=False),
    )
    asm.add_joint(slider)
    slider.set_offset(20.0)  # slides along the rotated +Z = world +X
    assert _world(carriage.anchor("base")) == pytest.approx([220.0, 0.0, 0.0])
    j1.set_angle(math.pi / 2)
    assert _world(carriage.anchor("base")) == pytest.approx([100.0, 120.0, 0.0])


def test_rigid_joint_public_resolve_after_manual_edit():
    asm, (a, b, c), _ = _chain()
    hand = _link(10.0)
    rigid = _rigid(c.anchor("tip"), hand.anchor("base"))
    asm.add_joint(rigid)
    # Move the parent anchor itself (e.g. a re-dimensioned part): the joint
    # has no DOF setter, so resolve() is the public way to re-place it.
    c.anchor("tip").frame.position = [50.0, 0.0, 0.0]
    assert _world(hand.anchor("base")) == pytest.approx([300.0, 0.0, 0.0])
    assert rigid.resolve() is True
    assert _world(hand.anchor("base")) == pytest.approx([250.0, 0.0, 0.0])


def test_assembly_resolve_replaces_every_joint():
    asm, (_, b, c), (j1, j2) = _chain()
    b.anchor("tip").frame.position = [40.0, 0.0, 0.0]
    assert asm.resolve() is True
    assert _world(c.anchor("base")) == pytest.approx([140.0, 0.0, 0.0])
    # Idempotent.
    asm.resolve()
    assert _world(c.anchor("base")) == pytest.approx([140.0, 0.0, 0.0])


def test_unplaced_joint_resolve_is_noop():
    a, b = _link(), _link()
    joint = _revolute(a.anchor("tip"), b.anchor("base"))
    assert joint.resolve() is False
    assert joint.set_angle(1.0) is True


def test_cascade_survives_to_dag():
    asm, (_, _, c), (j1, _) = _chain()
    asm.to_dag()
    j1.set_angle(math.pi / 2)
    assert _world(c.anchor("base")) == pytest.approx([100.0, 100.0, 0.0])
    asm.to_dag()
    j1.set_angle(0.0)
    assert _world(c.anchor("base")) == pytest.approx([200.0, 0.0, 0.0])


# --------------------------------------------------------------------------- #
# 2. Joints inside a placed sub-assembly (sesame_robot leg structure)
# --------------------------------------------------------------------------- #


class Leg(Assembly):
    """hip servo -> (revolute) thigh -> (revolute) shin -> (rigid) foot."""

    def __init__(self):
        self.servo = _link(20.0)
        self.thigh = _link(50.0)
        self.shin = _link(40.0)
        self.foot = _link(10.0)
        self.ground(self.servo.anchor("base"))
        self.hip = _revolute(self.servo.anchor("tip"), self.thigh.anchor("base"))
        self.knee = _revolute(self.thigh.anchor("tip"), self.shin.anchor("base"))
        self.add_joint(self.hip)
        self.add_joint(self.knee)
        self.add_joint(_rigid(self.shin.anchor("tip"), self.foot.anchor("base")))
        self.add_anchor(_anchor("mount", [0.0, 0.0, 0.0]))


def _robot():
    body = _link(30.0)
    robot = Assembly()
    robot.ground(body.anchor("base"))
    leg = Leg()
    robot.add_joint(_rigid(body.anchor("tip"), leg.anchor("mount")))
    return robot, body, leg


def test_set_angle_inside_placed_subassembly():
    _, _, leg = _robot()
    # Leg mounted at x=30: servo tip 50, thigh tip 100, shin tip 140, foot 150.
    assert _world(leg.foot.anchor("tip")) == pytest.approx([150.0, 0.0, 0.0])

    leg.hip.set_angle(math.pi / 2)  # used to raise "does not chain up to 'origin'"

    assert _world(leg.thigh.anchor("tip")) == pytest.approx([50.0, 50.0, 0.0])
    assert _world(leg.shin.anchor("tip")) == pytest.approx([50.0, 90.0, 0.0])
    assert _world(leg.foot.anchor("tip")) == pytest.approx([50.0, 100.0, 0.0])

    leg.knee.set_angle(-math.pi / 2)
    assert _world(leg.foot.anchor("tip")) == pytest.approx([100.0, 50.0, 0.0])


def test_subassembly_cascade_reaches_parent_joints():
    """A part jointed in the robot onto a leg part follows the leg's joint."""
    robot, _, leg = _robot()
    sensor = _link(5.0)
    robot.add_joint(_rigid(leg.foot.anchor("tip"), sensor.anchor("base")))
    assert _world(sensor.anchor("tip")) == pytest.approx([155.0, 0.0, 0.0])

    leg.hip.set_angle(math.pi / 2)

    assert _world(sensor.anchor("base")) == pytest.approx([50.0, 100.0, 0.0])
    assert _world(sensor.anchor("tip")) == pytest.approx([50.0, 105.0, 0.0])


def test_subassembly_mounted_by_moving_anchor_is_replaced():
    """The robot mates the leg by an anchor on a link the leg itself moves."""
    body = _link(30.0)
    robot = Assembly()
    robot.ground(body.anchor("base"))
    leg = Leg()
    # A leg-level anchor that rides on the shin (its frame chains through the
    # shin, so the leg's own knee/hip joints move it).
    knee_mount = _anchor("knee_mount", [0.0, 0.0, 0.0])
    knee_mount.frame.top_frame = leg.shin.anchor("base").frame
    leg.add_anchor(knee_mount)
    robot.add_joint(_rigid(body.anchor("tip"), knee_mount))
    assert _world(leg.shin.anchor("base")) == pytest.approx([30.0, 0.0, 0.0])

    leg.hip.set_angle(math.pi / 2)

    # The leg folds about the hip but stays rigidly mated at the shin base:
    # same position AND orientation, so the rest of the leg swings -90° about
    # the mount. Servo tip in leg space is (20, 0), 50 below the shin base.
    shin_t, shin_q = tf_relative_to_frame(leg.shin.anchor("base").frame)
    assert shin_t == pytest.approx([30.0, 0.0, 0.0])
    assert shin_q == pytest.approx([1.0, 0.0, 0.0, 0.0], abs=1e-9)
    assert _world(leg.servo.anchor("tip")) == pytest.approx([-20.0, 0.0, 0.0])


def test_robot_to_dag_after_leg_set_angle():
    robot, _, leg = _robot()
    robot.to_dag()
    leg.hip.set_angle(0.3)
    leg.knee.set_angle(-0.6)
    dag = robot.to_dag()
    assert dag
    thigh_len, shin_len, foot_len = 50.0, 40.0, 10.0
    x = 50.0 + thigh_len * math.cos(0.3) + (shin_len + foot_len) * math.cos(-0.3)
    y = thigh_len * math.sin(0.3) + (shin_len + foot_len) * math.sin(-0.3)
    assert _world(leg.foot.anchor("tip")) == pytest.approx([x, y, 0.0])
