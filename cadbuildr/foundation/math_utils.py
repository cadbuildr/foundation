"""Math utilities for vector and quaternion operations."""

import numpy as np
from typing import Sequence


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


def create_frame_from_xdir_and_normal(
    base_frame, x_dir: list[float], normal: list[float], name: str
):
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
