"""Math utilities for vector and quaternion operations."""

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
    rotated = quaternion_multiply(quaternion_multiply(list(q), qv), quaternion_conjugate(q))
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


def tf_relative_to_frame(
    frame: Any, ancestor_frame: Any = None
) -> tuple[list[float], list[float]]:
    """Transform of ``frame`` expressed in ``ancestor_frame`` coordinates.

    Walks the ``top_frame`` chain from ``frame`` up to (excluding)
    ``ancestor_frame``, composing local transforms. With ``ancestor_frame=None``
    the walk continues to the root frame. Identity comparison (``is``) is used
    on purpose: structurally equal frames at different tree positions must not
    terminate the walk.
    """
    chain = []
    cursor = frame
    while cursor is not None and cursor is not ancestor_frame:
        chain.append(cursor)
        cursor = cursor.top_frame
    if ancestor_frame is not None and cursor is not ancestor_frame:
        raise ValueError(
            f"Frame '{frame.name.value}' does not chain up to frame "
            f"'{ancestor_frame.name.value}'. Anchors must belong to a component "
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
        base_frame: Base frame to derive position from
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

    # Get position from base frame
    position = base_frame.position

    # Create new frame with same position but different quaternion
    # Set top_frame to base_frame (the part's frame) to match old foundation behavior
    # This creates a frame hierarchy: part.frame -> plane.frame
    return Frame(
        top_frame=base_frame,
        name=StringParameter(value=name),
        display=BoolParameter(value=False),
        position=position,
        quaternion=quaternion,
    )
