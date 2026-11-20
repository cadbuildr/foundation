"""Assembly placement helpers: explicit poses and kinematic loop closure.

Two hand-written pieces sit on top of the anchor/joint model:

* :func:`rotation_from_deg` turns the ``rot_deg=`` argument of
  ``Assembly.add_component`` / ``Assembly.ground`` into a quaternion. Angles
  are always **degrees** here (the keyword says so); joint DOF values and
  ``Anchor.rotated`` stay in radians.
* :func:`check_loop_closure` verifies a joint between two components that are
  *both* already placed. Such a joint places nothing (a component has exactly
  one placement); instead its two anchors must already agree, up to the
  joint's free degrees of freedom. ``Assembly.add_connection`` runs it
  automatically and raises :class:`LoopClosureError` when they do not.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Any, Sequence, Union

from .math_utils import (
    axis_angle_to_quaternion,
    compose_tf,
    invert_tf,
    quaternion_inverse,
    quaternion_multiply,
    tf_relative_to_frame,
)

RotDeg = Union[float, Sequence[float]]

#: Default loop-closure tolerances (mm, degrees).
DEFAULT_POS_TOL = 0.05
DEFAULT_ANGLE_TOL_DEG = 0.1

_FLIP_Q = [0.0, 1.0, 0.0, 0.0]  # 180° about local X (face-to-face mate)


class LoopClosureError(ValueError):
    """A joint closing a kinematic loop connects anchors that do not meet."""


def rotation_from_deg(rot_deg: RotDeg) -> list[float]:
    """Quaternion ``[w, x, y, z]`` for a rotation given in degrees.

    * a number ``a`` rotates by ``a`` degrees about +Z;
    * ``(rx, ry, rz)`` rotates about the fixed X axis by ``rx``, then about
      the fixed Y axis by ``ry``, then about the fixed Z axis by ``rz``
      (``R = Rz · Ry · Rx``).
    """
    if isinstance(rot_deg, Real):
        return axis_angle_to_quaternion([0.0, 0.0, 1.0], math.radians(float(rot_deg)))
    if hasattr(rot_deg, "tolist"):
        rot_deg = rot_deg.tolist()
    values = [float(v) for v in rot_deg]
    if len(values) != 3:
        raise ValueError(
            "rot_deg must be a number (degrees about +Z) or (rx, ry, rz) in "
            f"degrees about the fixed X, Y, Z axes; got {len(values)} values"
        )
    rx, ry, rz = (math.radians(v) for v in values)
    q = axis_angle_to_quaternion([1.0, 0.0, 0.0], rx)
    q = quaternion_multiply(axis_angle_to_quaternion([0.0, 1.0, 0.0], ry), q)
    return quaternion_multiply(axis_angle_to_quaternion([0.0, 0.0, 1.0], rz), q)


def _rotation_angle(q: Sequence[float]) -> float:
    """Rotation angle (radians, in [0, π]) of a unit quaternion."""
    vec = math.sqrt(q[1] ** 2 + q[2] ** 2 + q[3] ** 2)
    return 2.0 * math.atan2(vec, abs(q[0]))


def _swing_twist_z(q: Sequence[float]) -> tuple[float, float]:
    """Split ``q`` into a twist about +Z and the remaining swing.

    Returns ``(twist_angle, swing_angle)`` in radians. The swing is the part
    of the rotation a revolute-style joint cannot absorb.
    """
    w, z = q[0], q[3]
    norm = math.hypot(w, z)
    if norm < 1e-12:
        # Pure 180° swing about an in-plane axis: no twist component.
        return 0.0, math.pi
    twist = [w / norm, 0.0, 0.0, z / norm]
    swing = quaternion_multiply(list(q), quaternion_inverse(twist))
    twist_angle = 2.0 * math.atan2(twist[3], twist[0])
    return twist_angle, _rotation_angle(swing)


# Per joint type: which translation axes are free and how rotation may vary
# ("none", "z" = about the anchor +Z, "all"), all in the parent anchor frame.
_FREE_DOFS: dict[str, tuple[tuple[bool, bool, bool], str]] = {
    "RigidJoint": ((False, False, False), "none"),
    "RevoluteJoint": ((False, False, False), "z"),
    "SliderJoint": ((False, False, True), "none"),
    "CylindricalJoint": ((False, False, True), "z"),
    "PlanarJoint": ((True, True, False), "z"),
    "BallJoint": ((False, False, False), "all"),
    "PinSlotJoint": ((True, False, False), "z"),
    "ScrewJoint": ((False, False, True), "z"),
}


def loop_closure_error(joint: Any, assembly: Any) -> tuple[float, float]:
    """``(position_error_mm, angle_error_deg)`` of a loop-closing joint.

    Both anchors are resolved in ``assembly`` space. The joint's own motion
    ``J = P⁻¹ · C · F⁻¹`` (P parent anchor, C child anchor, F the face-to-face
    flip) must lie in the joint's free DOFs; whatever does not is the error.
    """
    type_name = type(joint).__name__
    if type_name not in _FREE_DOFS:
        raise TypeError(f"Unsupported joint type '{type_name}'")
    free_t, free_r = _FREE_DOFS[type_name]

    from .compute_functions import component_frames

    frames = component_frames(assembly)
    p_t, p_q = tf_relative_to_frame(joint.parent_anchor.frame, frames)
    c_t, c_q = tf_relative_to_frame(joint.child_anchor.frame, frames)
    j_t, j_q = compose_tf(*invert_tf(p_t, p_q), c_t, c_q)
    if joint.flip.value:
        j_t, j_q = compose_tf(j_t, j_q, *invert_tf([0.0, 0.0, 0.0], _FLIP_Q))

    residual = [0.0 if free_t[i] else j_t[i] for i in range(3)]
    if free_r == "all":
        angle_err = 0.0
    elif free_r == "z":
        twist, angle_err = _swing_twist_z(j_q)
        if type_name == "ScrewJoint":
            # Travel is pitch-coupled to the twist; only check it modulo one
            # pitch (the twist angle itself is only known modulo a full turn).
            pitch = float(joint.pitch.value)
            if pitch:
                expected = twist / (2.0 * math.pi) * pitch
                off = (j_t[2] - expected) % pitch
                residual[2] = min(off, pitch - off)
    else:
        angle_err = _rotation_angle(j_q)
    pos_err = math.sqrt(sum(r * r for r in residual))
    return pos_err, math.degrees(angle_err)


def check_loop_closure(
    joint: Any,
    assembly: Any,
    pos_tol: float = DEFAULT_POS_TOL,
    angle_tol_deg: float = DEFAULT_ANGLE_TOL_DEG,
    label: str = "connection",
) -> None:
    """Raise :class:`LoopClosureError` when a loop-closing joint's anchors
    disagree by more than ``pos_tol`` mm or ``angle_tol_deg`` degrees."""
    pos_err, angle_err = loop_closure_error(joint, assembly)
    if pos_err > pos_tol or angle_err > angle_tol_deg:
        raise LoopClosureError(
            f"'{label}' closes a kinematic loop but its anchors do not meet: "
            f"'{joint.parent_anchor.name.value}' and "
            f"'{joint.child_anchor.name.value}' are off by {pos_err:.3f} mm and "
            f"{angle_err:.3f}° for a {type(joint).__name__} (tolerance "
            f"{pos_tol:g} mm / {angle_tol_deg:g}°). Both components are already "
            "placed, so this joint cannot move either one: check the dimensions "
            "around the loop."
        )
