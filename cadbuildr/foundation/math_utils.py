"""Math utilities for vector and quaternion operations.

Angle convention for the whole 3D API (Part/Assembly.rotate, Anchor.rotated,
TFHelper.rotate, axis_angle_to_quaternion): **radians**. Degree variants say
so in their name (``rotate_deg``, ``rotated_deg``) or keyword (``angle_deg=``).
Sketch-level patterns (``PolarLocations``) take degrees, also named ``*_deg``.
"""

import math

import numpy as np
from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from .gen.models import Frame


def rotation_matrix_to_quaternion(rot_matrix: np.ndarray) -> list[float]:
    """Convert a 3x3 rotation matrix to a quaternion [w, x, y, z].

    Args:
        rot_matrix: 3x3 rotation matrix as numpy array

    Returns:
        Quaternion as [w, x, y, z]
    """
    trace = np.trace(rot_matrix)
    if trace > 0:
        s = np.sqrt(trace + 1.0) * 2  # s = 4 * qw
        w = 0.25 * s
        x = (rot_matrix[2, 1] - rot_matrix[1, 2]) / s
        y = (rot_matrix[0, 2] - rot_matrix[2, 0]) / s
        z = (rot_matrix[1, 0] - rot_matrix[0, 1]) / s
    else:
        if rot_matrix[0, 0] > rot_matrix[1, 1] and rot_matrix[0, 0] > rot_matrix[2, 2]:
            s = (
                np.sqrt(1.0 + rot_matrix[0, 0] - rot_matrix[1, 1] - rot_matrix[2, 2])
                * 2
            )
            w = (rot_matrix[2, 1] - rot_matrix[1, 2]) / s
            x = 0.25 * s
            y = (rot_matrix[0, 1] + rot_matrix[1, 0]) / s
            z = (rot_matrix[0, 2] + rot_matrix[2, 0]) / s
        elif rot_matrix[1, 1] > rot_matrix[2, 2]:
            s = (
                np.sqrt(1.0 + rot_matrix[1, 1] - rot_matrix[0, 0] - rot_matrix[2, 2])
                * 2
            )
            w = (rot_matrix[0, 2] - rot_matrix[2, 0]) / s
            x = (rot_matrix[0, 1] + rot_matrix[1, 0]) / s
            y = 0.25 * s
            z = (rot_matrix[1, 2] + rot_matrix[2, 1]) / s
        else:
            s = (
                np.sqrt(1.0 + rot_matrix[2, 2] - rot_matrix[0, 0] - rot_matrix[1, 1])
                * 2
            )
            w = (rot_matrix[1, 0] - rot_matrix[0, 1]) / s
            x = (rot_matrix[0, 2] + rot_matrix[2, 0]) / s
            y = (rot_matrix[1, 2] + rot_matrix[2, 1]) / s
            z = 0.25 * s
    return [w, x, y, z]


def quaternion_to_axes(
    quaternion: list[float],
) -> tuple[list[float], list[float], list[float]]:
    """Convert quaternion [w, x, y, z] to x, y, z axes vectors.

    Args:
        quaternion: Quaternion as [w, x, y, z]

    Returns:
        Tuple of (x_axis, y_axis, z_axis) as lists
    """
    w, x, y, z = quaternion[0], quaternion[1], quaternion[2], quaternion[3]

    # X-axis (first column of rotation matrix)
    x_axis = [1 - 2 * (y * y + z * z), 2 * (x * y + w * z), 2 * (x * z - w * y)]

    # Y-axis (second column of rotation matrix)
    y_axis = [2 * (x * y - w * z), 1 - 2 * (x * x + z * z), 2 * (y * z + w * x)]

    # Z-axis (third column of rotation matrix)
    z_axis = [2 * (x * z + w * y), 2 * (y * z - w * x), 1 - 2 * (x * x + y * y)]

    return x_axis, y_axis, z_axis


def axis_angle_to_quaternion(axis: Sequence[float], angle: float) -> list[float]:
    """Convert axis-angle representation to quaternion [w, x, y, z].

    Args:
        axis: Rotation axis as [x, y, z]
        angle: Rotation angle in radians

    Returns:
        Quaternion as [w, x, y, z]
    """
    import math

    # Normalize axis
    length = math.sqrt(axis[0] ** 2 + axis[1] ** 2 + axis[2] ** 2)
    if length == 0:
        return [1.0, 0.0, 0.0, 0.0]

    nx, ny, nz = axis[0] / length, axis[1] / length, axis[2] / length
    half_angle = angle / 2
    sin_half = math.sin(half_angle)
    cos_half = math.cos(half_angle)

    return [cos_half, nx * sin_half, ny * sin_half, nz * sin_half]


def quaternion_multiply(q1: list[float], q2: list[float]) -> list[float]:
    """Multiply two quaternions [w, x, y, z].

    Args:
        q1: First quaternion as [w, x, y, z]
        q2: Second quaternion as [w, x, y, z]

    Returns:
        Product quaternion as [w, x, y, z]
    """
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2

    return [
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    ]


def quaternion_conjugate(q: Sequence[float]) -> list[float]:
    """Conjugate of quaternion [w, x, y, z]."""
    return [q[0], -q[1], -q[2], -q[3]]


def quaternion_inverse(q: Sequence[float]) -> list[float]:
    """Inverse of quaternion [w, x, y, z]."""
    norm_sq = q[0] ** 2 + q[1] ** 2 + q[2] ** 2 + q[3] ** 2
    if norm_sq == 0:
        raise ValueError("Cannot invert a zero quaternion")
    conj = quaternion_conjugate(q)
    return [c / norm_sq for c in conj]


def quaternion_rotate_vector(q: Sequence[float], v: Sequence[float]) -> list[float]:
    """Rotate vector [x, y, z] by quaternion [w, x, y, z]."""
    qv = [0.0, float(v[0]), float(v[1]), float(v[2])]
    rotated = quaternion_multiply(
        quaternion_multiply(list(q), qv), quaternion_conjugate(q)
    )
    return [rotated[1], rotated[2], rotated[3]]


def compose_tf(
    t1: Sequence[float],
    q1: Sequence[float],
    t2: Sequence[float],
    q2: Sequence[float],
) -> tuple[list[float], list[float]]:
    """Compose two rigid transforms: result = T1 ∘ T2 (apply T2, then T1).

    Matches the viewer's frame-chain composition (rotate then translate per
    frame walking up the ``top_frame`` chain): ``p_out = R(q1)·(R(q2)·p + t2) + t1``.
    """
    rotated_t2 = quaternion_rotate_vector(q1, t2)
    translation = [float(t1[i]) + rotated_t2[i] for i in range(3)]
    quaternion = quaternion_multiply(list(q1), list(q2))
    return translation, quaternion


def invert_tf(
    t: Sequence[float], q: Sequence[float]
) -> tuple[list[float], list[float]]:
    """Invert a rigid transform (translation, quaternion)."""
    q_inv = quaternion_inverse(q)
    t_inv = quaternion_rotate_vector(q_inv, [-float(t[0]), -float(t[1]), -float(t[2])])
    return t_inv, q_inv


# Instance attribute (on a Frame) holding the list of frames that stand for
# the same coordinate system: an Assembly's own frame and the fresh root
# frames ``_convert_component_to_root`` gives it each time it is placed in a
# parent or serialised (``to_dag`` / ``show_dag``). The list object is shared
# by every member of the group.
_FRAME_ALIASES_ATTR = "_frame_aliases"


def frame_aliases(frame: Any) -> list[Any]:
    """Every frame that stands for the same coordinate system as ``frame``
    (``frame`` itself first). An Assembly's frame and the root frames created
    when it is nested or serialised are aliases of one another."""
    if frame is None:
        return []
    group = getattr(frame, "__dict__", {}).get(_FRAME_ALIASES_ATTR)
    if not group:
        return [frame]
    return [frame, *(f for f in group if f is not frame)]


def link_frame_aliases(frame: Any, alias: Any) -> None:
    """Record that ``alias`` stands for the same coordinate system as
    ``frame`` (see :func:`frame_aliases`)."""
    group = frame.__dict__.get(_FRAME_ALIASES_ATTR)
    if group is None:
        group = [frame]
    other = alias.__dict__.get(_FRAME_ALIASES_ATTR) or [alias]
    for f in other:
        if not any(f is g for g in group):
            group.append(f)
    for f in group:
        # Bypass pydantic: a private, non-field attribute (ignored by ==,
        # serialisation and the DAG).
        object.__setattr__(f, _FRAME_ALIASES_ATTR, group)


def tf_relative_to_frame(
    frame: Any, ancestor_frame: Any = None
) -> tuple[list[float], list[float]]:
    """Transform of ``frame`` expressed in ``ancestor_frame`` coordinates.

    Walks the ``top_frame`` chain from ``frame`` up to (excluding)
    ``ancestor_frame``, composing local transforms. With ``ancestor_frame=None``
    the walk continues to the root frame. Identity comparison (``is``) is used
    on purpose: structurally equal frames at different tree positions must not
    terminate the walk.

    ``ancestor_frame`` may also be a list/tuple of frames that all stand for
    the same coordinate system (an assembly's own frame and the frames of the
    roots created from it when it was placed); the walk stops at the first one
    it meets. Aliases of a stop frame (:func:`frame_aliases`) count too, so an
    assembly's ``frame`` keeps working as ``ancestor_frame`` after the
    assembly was nested in another one or serialised with ``show_dag`` /
    ``to_dag`` (which re-root its children onto a fresh frame).
    """
    if isinstance(ancestor_frame, (list, tuple)):
        given = list(ancestor_frame)
    elif ancestor_frame is None:
        given = []
    else:
        given = [ancestor_frame]
    stops: list[Any] = []
    for stop in given:
        for alias in frame_aliases(stop):
            if not any(alias is s for s in stops):
                stops.append(alias)
    chain = []
    cursor = frame
    while cursor is not None and not any(cursor is stop for stop in stops):
        chain.append(cursor)
        cursor = cursor.top_frame
    if stops and cursor is None:
        raise ValueError(
            f"Frame '{frame.name.value}' does not chain up to frame "
            f"'{stops[0].name.value}'. Anchors must belong to a component "
            "already placed under the assembly."
        )
    translation, quaternion = [0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]
    for f in reversed(chain):
        translation, quaternion = compose_tf(
            translation, quaternion, f.position, f.quaternion
        )
    return translation, quaternion


def create_frame_from_xdir_and_normal(
    base_frame: Any, x_dir: list[float], normal: list[float], name: str
) -> "Frame":
    """Create a new frame from x direction and normal vectors.

    Args:
        base_frame: Parent frame (the new frame sits at its origin)
        x_dir: X direction vector
        normal: Normal vector (Z direction)
        name: Name for the new frame

    Returns:
        New Frame instance
    """
    from .gen.models import Frame, StringParameter, BoolParameter

    # Normalize vectors
    x_dir_arr = np.array(x_dir, dtype=float)
    normal_arr = np.array(normal, dtype=float)
    x_dir_arr = x_dir_arr / np.linalg.norm(x_dir_arr)
    normal_arr = normal_arr / np.linalg.norm(normal_arr)

    # Compute y axis as cross product of normal and x_dir
    y_axis = np.cross(normal_arr, x_dir_arr)
    y_axis = y_axis / np.linalg.norm(y_axis)

    # Form rotation matrix [x_dir, y_axis, normal] as columns
    rot_matrix = np.array([x_dir_arr, y_axis, normal_arr]).T

    # Convert to quaternion
    quaternion = rotation_matrix_to_quaternion(rot_matrix)

    # The new frame is a child of base_frame (hierarchy: part.frame -> plane.frame),
    # so it sits at the parent's origin with a purely LOCAL rotation. Copying
    # base_frame.position here as well applied the parent offset twice once the
    # part had been translated before its first xz()/yz()/... call.
    return Frame(
        top_frame=base_frame,
        name=StringParameter(value=name),
        display=BoolParameter(value=False),
        position=[0.0, 0.0, 0.0],
        quaternion=quaternion,
    )


# --------------------------------------------------------------------------- #
# Orientation from directions (make_anchor(z_axis=, x_axis=), anchor patterns).
# --------------------------------------------------------------------------- #

# Below this length a direction is treated as the zero vector.
_ZERO_EPS = 1e-12
# Below this sine of the angle between two directions they count as parallel.
_PARALLEL_SIN_EPS = 1e-6


def unit_vector(v: Sequence[float], label: str = "vector") -> np.ndarray:
    """Normalised 3-vector; ``ValueError`` for a wrong length or zero vector."""
    arr = np.asarray([float(c) for c in v], dtype=float)
    if arr.shape != (3,):
        raise ValueError(f"{label} must have exactly 3 components, got {len(arr)}")
    norm = float(np.linalg.norm(arr))
    if norm < _ZERO_EPS:
        raise ValueError(f"{label} must be a non-zero direction, got {list(v)}")
    return arr / norm


def default_x_for_z(z_axis: Sequence[float]) -> list[float]:
    """Stable X direction for a frame whose Z is ``z_axis``.

    Rule: X is the image of world +X under the *shortest rotation* taking
    world +Z onto ``z_axis``. So ``z=+Z`` gives ``x=+X`` (identity), a ``z``
    in the XZ plane keeps Y fixed (``z=+X`` gives ``x=-Z``), and the one
    ambiguous case ``z=-Z`` resolves to 180° about X — exactly
    ``make_anchor(z_down=True)``, i.e. ``x=+X``. Closed form:
    ``x = (1 - zx²/(1+zz), -zx·zy/(1+zz), -zx)``.
    """
    z = unit_vector(z_axis, "z_axis")
    if 1.0 + z[2] < _PARALLEL_SIN_EPS:
        return [1.0, 0.0, 0.0]
    k = 1.0 / (1.0 + z[2])
    x = np.array([1.0 - z[0] * z[0] * k, -z[0] * z[1] * k, -z[0]])
    return (x / float(np.linalg.norm(x))).tolist()


def _perpendicular_part(
    vector: Sequence[float], axis: np.ndarray, label: str, axis_label: str
) -> np.ndarray:
    hint = unit_vector(vector, label)
    perp = hint - float(np.dot(hint, axis)) * axis
    norm = float(np.linalg.norm(perp))
    if norm < _PARALLEL_SIN_EPS:
        raise ValueError(
            f"{label} {list(vector)} is parallel to {axis_label} "
            f"{axis.tolist()}; pass a {label} with a component perpendicular "
            f"to {axis_label}"
        )
    return perp / norm


def axes_from_directions(
    z_axis: Sequence[float], x_axis: Sequence[float] | None = None
) -> tuple[list[float], list[float], list[float]]:
    """Right-handed orthonormal (x, y, z) from a primary Z and an X hint.

    ``z_axis`` is kept exactly (normalised). ``x_axis`` is a hint: its
    component along Z is projected off and the rest normalised. When
    ``x_axis`` is omitted, :func:`default_x_for_z` picks it. Raises
    ``ValueError`` for zero-length axes or an ``x_axis`` parallel to
    ``z_axis``.
    """
    z = unit_vector(z_axis, "z_axis")
    if x_axis is None:
        x = np.asarray(default_x_for_z(z), dtype=float)
    else:
        x = _perpendicular_part(x_axis, z, "x_axis", "z_axis")
    y = np.cross(z, x)
    return x.tolist(), y.tolist(), z.tolist()


def axes_from_x_and_up(
    x_axis: Sequence[float], up: Sequence[float]
) -> tuple[list[float], list[float], list[float]]:
    """Orthonormal (x, y, z) keeping ``x_axis`` exact, Z towards ``up``.

    The X-primary twin of :func:`axes_from_directions` (used by
    ``Anchor.along_path`` where X must follow the tangent exactly).
    """
    x = unit_vector(x_axis, "x_axis")
    z = _perpendicular_part(up, x, "up", "x_axis")
    y = np.cross(z, x)
    return x.tolist(), y.tolist(), z.tolist()


def quaternion_from_axes(
    x_axis: Sequence[float], y_axis: Sequence[float], z_axis: Sequence[float]
) -> list[float]:
    """Quaternion [w, x, y, z] of the rotation whose columns are x, y, z.

    The sign is normalised to ``w >= 0`` so equal rotations serialise equally.
    """
    rot = np.array([list(x_axis), list(y_axis), list(z_axis)], dtype=float).T
    q = [float(c) for c in rotation_matrix_to_quaternion(rot)]
    norm = math.sqrt(sum(c * c for c in q))
    q = [c / norm for c in q]
    if q[0] < 0.0:
        q = [-c for c in q]
    return q


def quaternion_from_directions(
    z_axis: Sequence[float], x_axis: Sequence[float] | None = None
) -> list[float]:
    """Quaternion for a frame with Z along ``z_axis`` and X towards ``x_axis``.

    See :func:`axes_from_directions` for the orthonormalisation rule.
    """
    return quaternion_from_axes(*axes_from_directions(z_axis, x_axis))
