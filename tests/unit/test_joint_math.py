"""Tests for the rigid-transform math used by anchor/joint resolution."""

import math

import pytest

from cadbuildr.foundation.gen.models import (
    BoolParameter,
    Frame,
    StringParameter,
)
from cadbuildr.foundation.math_utils import (
    axis_angle_to_quaternion,
    compose_tf,
    invert_tf,
    quaternion_conjugate,
    quaternion_inverse,
    quaternion_rotate_vector,
    tf_relative_to_frame,
)


def _frame(name, position, quaternion, top_frame=None):
    return Frame(
        top_frame=top_frame,
        name=StringParameter(value=name),
        display=BoolParameter(value=False),
        position=list(position),
        quaternion=list(quaternion),
    )


def _assert_close(actual, expected, tol=1e-9):
    assert len(actual) == len(expected)
    for a, e in zip(actual, expected):
        assert a == pytest.approx(e, abs=tol)


IDENTITY_Q = [1.0, 0.0, 0.0, 0.0]


def test_quaternion_conjugate_and_inverse():
    q = axis_angle_to_quaternion([0, 0, 1], math.pi / 3)
    assert quaternion_conjugate(q) == [q[0], -q[1], -q[2], -q[3]]
    # q * q^-1 = identity for a unit quaternion
    from cadbuildr.foundation.math_utils import quaternion_multiply

    _assert_close(quaternion_multiply(q, quaternion_inverse(q)), IDENTITY_Q)


def test_quaternion_inverse_zero_raises():
    with pytest.raises(ValueError):
        quaternion_inverse([0.0, 0.0, 0.0, 0.0])


def test_rotate_vector_quarter_turn_about_z():
    q = axis_angle_to_quaternion([0, 0, 1], math.pi / 2)
    _assert_close(quaternion_rotate_vector(q, [1, 0, 0]), [0, 1, 0])
    _assert_close(quaternion_rotate_vector(q, [0, 1, 0]), [-1, 0, 0])


def test_compose_tf_translation_then_rotation():
    # T1 rotates 90° about Z; composing with a pure translation T2 rotates
    # T2's translation into T1's space: p = R(q1)·t2 + t1.
    q1 = axis_angle_to_quaternion([0, 0, 1], math.pi / 2)
    t, q = compose_tf([1, 0, 0], q1, [1, 0, 0], IDENTITY_Q)
    _assert_close(t, [1, 1, 0])
    _assert_close(q, q1)


def test_invert_tf_roundtrip():
    q = axis_angle_to_quaternion([0.3, -0.5, 0.81], 1.234)
    t = [3.0, -2.0, 7.5]
    ti, qi = invert_tf(t, q)
    t_round, q_round = compose_tf(t, q, ti, qi)
    _assert_close(t_round, [0, 0, 0])
    _assert_close([abs(q_round[0])] + q_round[1:], IDENTITY_Q)


def test_tf_relative_to_frame_three_deep_chain():
    # root -> a (translate x+10) -> b (rotate 90° about Z) -> c (translate y+5)
    root = _frame("root", [0, 0, 0], IDENTITY_Q)
    a = _frame("a", [10, 0, 0], IDENTITY_Q, top_frame=root)
    qz90 = axis_angle_to_quaternion([0, 0, 1], math.pi / 2)
    b = _frame("b", [0, 0, 0], qz90, top_frame=a)
    c = _frame("c", [0, 5, 0], IDENTITY_Q, top_frame=b)

    t, q = tf_relative_to_frame(c, root)
    # c's local +y offset is rotated by b's 90° about Z: [0,5,0] -> [-5,0,0]
    _assert_close(t, [5, 0, 0])
    _assert_close(q, qz90)


def test_tf_relative_to_frame_walks_to_absolute_root_when_no_ancestor():
    root = _frame("root", [1, 2, 3], IDENTITY_Q)
    leaf = _frame("leaf", [4, 5, 6], IDENTITY_Q, top_frame=root)
    t, _ = tf_relative_to_frame(leaf, None)
    _assert_close(t, [5, 7, 9])


def test_tf_relative_to_frame_unreachable_ancestor_raises():
    lineage_root = _frame("root", [0, 0, 0], IDENTITY_Q)
    leaf = _frame("leaf", [1, 0, 0], IDENTITY_Q, top_frame=lineage_root)
    stranger = _frame("stranger", [0, 0, 0], IDENTITY_Q)
    with pytest.raises(ValueError, match="does not chain up to"):
        tf_relative_to_frame(leaf, stranger)


def test_tf_relative_to_frame_uses_identity_not_equality():
    # Two structurally identical frames must not terminate the walk early:
    # the ancestor check is object identity, not pydantic equality.
    ancestor = _frame("origin", [0, 0, 0], IDENTITY_Q)
    lookalike = _frame("origin", [0, 0, 0], IDENTITY_Q)
    leaf = _frame("leaf", [2, 0, 0], IDENTITY_Q, top_frame=ancestor)
    assert lookalike == ancestor  # structural equality holds...
    with pytest.raises(ValueError):
        tf_relative_to_frame(leaf, lookalike)  # ...but identity is required
