"""A joint added in a sub-assembly may take its parent anchor from a sibling
component of an enclosing assembly (resolved through the common ancestor)."""

import pytest

from cadbuildr.foundation.gen.models import Assembly

from cadbuildr.foundation.compute_functions import (
    _anchor_owner,
    _tf_component_in_ancestor,
    tf_in_component,
)
from cadbuildr.foundation.math_utils import compose_tf, tf_relative_to_frame
from cadbuildr.foundation.gen.models import (
    Anchor,
    BoolParameter,
    Extrusion,
    Frame,
    Part,
    RevoluteJoint,
    RigidJoint,
    Sketch,
    Square,
    StringParameter,
)


# Self-contained helpers (a cross-test-module import breaks under Bazel's
# runfiles sandbox, where tests/unit is not on sys.path).
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
    return RevoluteJoint(
        parent_anchor=parent, child_anchor=child, flip=BoolParameter(value=False)
    )


def _rigid(parent, child):
    return RigidJoint(
        parent_anchor=parent, child_anchor=child, flip=BoolParameter(value=False)
    )


def _in(anchor, top):
    """Anchor position in ``top`` coordinates, through the placement chain."""
    owner = _anchor_owner(anchor)
    return compose_tf(
        *_tf_component_in_ancestor(owner, top), *tf_in_component(anchor.frame, owner)
    )[0]


def _approx(a, b):
    assert a == pytest.approx(b, abs=1e-9)


def _pcb(board_at=(0.0, 0.0, 0.0), group_at=(0.0, 0.0, 0.0)):
    """PCB pattern: top holds a board Part and a grouping sub-assembly."""
    board = _link(200.0)
    board.add_anchor(_anchor("place_R1", [30.0, 10.0, 2.0]))
    group = Assembly()
    top = Assembly()
    top.add_component(board, at=list(board_at))
    top.add_component(group, at=list(group_at))
    return top, board, group


def test_joint_in_subassembly_uses_sibling_anchor():
    top, board, group = _pcb()
    part = _link(5.0)
    group.add_joint(_rigid(board.anchor("place_R1"), part.anchor("base")))
    _approx(_in(part.anchor("base"), top), [30.0, 10.0, 2.0])


def test_offset_frames_are_composed():
    # Board and group frames do NOT coincide: the twin-anchor workaround
    # would be wrong here, the common-ancestor resolution is not.
    top, board, group = _pcb(board_at=(100.0, 0.0, 0.0), group_at=(0.0, 50.0, 0.0))
    part = _link(5.0)
    group.add_joint(_rigid(board.anchor("place_R1"), part.anchor("base")))
    _approx(_in(part.anchor("base"), top), [130.0, 10.0, 2.0])
    # Serialising re-roots the late-added child onto the group's placement:
    # the plain world walk then agrees.
    top.to_dag()
    _approx(tf_relative_to_frame(part.anchor("base").frame)[0], [130.0, 10.0, 2.0])


def test_nested_two_levels():
    top, board, group = _pcb(board_at=(100.0, 0.0, 0.0), group_at=(0.0, 50.0, 0.0))
    inner = Assembly()
    group.add_component(inner, at=[0.0, 0.0, 7.0])
    part = _link(5.0)
    inner.add_joint(_rigid(board.anchor("place_R1"), part.anchor("base")))
    _approx(_in(part.anchor("base"), top), [130.0, 10.0, 2.0])


def test_sibling_joint_follows_when_parent_moves():
    a = _link(100.0)
    top = Assembly()
    top.ground(a.anchor("base"))
    b = _link(100.0)
    j = _revolute(a.anchor("tip"), b.anchor("base"))
    top.add_joint(j)
    group = Assembly()
    top.add_component(group, at=[0.0, 20.0, 0.0])
    c = _link(10.0)
    group.add_joint(_rigid(b.anchor("tip"), c.anchor("base")))
    _approx(_in(c.anchor("base"), top), [200.0, 0.0, 0.0])
    j.set_angle(1.5707963267948966)
    _approx(_in(c.anchor("base"), top), [100.0, 100.0, 0.0])


def test_unrelated_anchor_still_errors():
    group = Assembly()
    stray = _link(10.0)
    part = _link(5.0)
    with pytest.raises(ValueError, match="common"):
        group.add_joint(_rigid(stray.anchor("tip"), part.anchor("base")))
