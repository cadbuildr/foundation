"""Derived planes (get_parallel_plane / get_angle_plane_from_axis) on any base plane.

A derived plane's Frame is a CHILD of the base plane's frame (``top_frame``),
and the kernel composes ``world = parent_world · local``. The frame must
therefore hold a purely LOCAL transform. It used to also bake in the parent's
position + quaternion, so the parent transform was applied twice — invisible
on a bare ``part.xy()`` (identity) but wrong for xz()/yz()/... and for chained
calls. Found converting BenchCAD parts (18/105 hit it).

``tf_relative_to_frame(frame)`` composes the chain exactly like the kernel's
``Frame`` (rotate-then-translate per frame walking up ``top_frame``).
"""

import math

import pytest

from cadbuildr.foundation import Part
from cadbuildr.foundation.math_utils import quaternion_rotate_vector, tf_relative_to_frame


def _world(plane):
    """(origin, x_axis, normal) of a plane in part coordinates, as the kernel sees it."""
    t, q = tf_relative_to_frame(plane.frame)
    return t, quaternion_rotate_vector(q, [1, 0, 0]), quaternion_rotate_vector(q, [0, 0, 1])


def _close(actual, expected):
    assert list(actual) == pytest.approx(list(expected), abs=1e-9)


# ---------------------------------------------------------------- parallel


def test_parallel_of_xy_is_unchanged_local_offset():
    part = Part()
    plane = part.xy().get_parallel_plane(10)
    _close(plane.frame.position, [0, 0, 10])
    _close(plane.frame.quaternion, [1, 0, 0, 0])
    origin, x_axis, normal = _world(plane)
    _close(origin, [0, 0, 10])
    _close(x_axis, [1, 0, 0])
    _close(normal, [0, 0, 1])


@pytest.mark.parametrize("base", ["xz", "yz", "yx", "zx", "zy"])
def test_parallel_offsets_along_base_normal_and_keeps_orientation(base):
    part = Part()
    base_plane = getattr(part, base)()
    b_origin, b_x, b_normal = _world(base_plane)
    origin, x_axis, normal = _world(base_plane.get_parallel_plane(5))
    _close(origin, [b_origin[i] + 5 * b_normal[i] for i in range(3)])
    _close(x_axis, b_x)
    _close(normal, b_normal)


def test_parallel_of_yz_bug_repro():
    # BenchCAD repro: a point at local (10, 20) on yz().get_parallel_plane(5)
    # must land at world (5, 10, 20) — it used to land at (20, 5, 10).
    part = Part()
    origin, x_axis, normal = _world(part.yz().get_parallel_plane(5))
    y_axis = [normal[1] * x_axis[2] - normal[2] * x_axis[1],
              normal[2] * x_axis[0] - normal[0] * x_axis[2],
              normal[0] * x_axis[1] - normal[1] * x_axis[0]]
    point = [origin[i] + 10 * x_axis[i] + 20 * y_axis[i] for i in range(3)]
    _close(point, [5, 10, 20])


def test_parallel_of_xz_bug_repro():
    # BenchCAD repro: xz().get_parallel_plane(10) has normal -Y at y=-10 (it
    # used to come out with normal -Z at z=-10).
    part = Part()
    origin, _, normal = _world(part.xz().get_parallel_plane(10))
    _close(origin, [0, -10, 0])
    _close(normal, [0, -1, 0])


def test_chained_parallel_planes_add_up():
    part = Part()
    plane = part.xy().get_parallel_plane(5).get_parallel_plane(3)
    origin, _, normal = _world(plane)
    _close(origin, [0, 0, 8])  # used to be 13 (5 + 5 + 3)
    _close(normal, [0, 0, 1])


def test_plane_axis_getters_report_composed_orientation():
    part = Part()
    plane = part.yz().get_parallel_plane(5)
    _close(plane.get_x_axis(), part.yz().get_x_axis())
    _close(plane.get_y_axis(), part.yz().get_y_axis())
    _close(plane.get_z_axis(), [1, 0, 0])


# ---------------------------------------------------------------- angle


def test_angle_plane_on_xy_is_unchanged():
    part = Part()
    origin, _, normal = _world(part.xy().get_angle_plane_from_axis([1, 0, 0], math.pi))
    _close(origin, [0, 0, 0])
    _close(normal, [0, 0, -1])


def test_angle_plane_axis_is_in_base_plane_local_coords():
    # BenchCAD repro (twisted_drill): rotating yz() about its own normal must
    # keep the normal along +X — it used to swing the normal to world Z.
    part = Part()
    base = part.yz()
    _, b_x, b_normal = _world(base)
    b_y = base.get_y_axis()
    _, x_axis, normal = _world(base.get_angle_plane_from_axis([0, 0, 1], math.pi / 2))
    _close(normal, b_normal)
    _close(x_axis, b_y)


def test_parallel_then_angle_flips_in_place():
    # holes_example pattern: a downward-facing plane at the top of a plate.
    part = Part()
    plane = part.xy().get_parallel_plane(4).get_angle_plane_from_axis([1, 0, 0], math.pi)
    origin, _, normal = _world(plane)
    _close(origin, [0, 0, 4])
    _close(normal, [0, 0, -1])


def test_angle_then_parallel_offsets_along_rotated_normal():
    part = Part()
    tilted = part.xy().get_angle_plane_from_axis([1, 0, 0], math.pi / 2)  # normal -> -Y
    origin, _, normal = _world(tilted.get_parallel_plane(7))
    _close(normal, [0, -1, 0])
    _close(origin, [0, -7, 0])


# ---------------------------------------------------------------- origin planes


def test_origin_planes_sit_at_part_origin_after_translate():
    # xz()/yz() frames are children of the part frame; copying the part's
    # position into them applied a pre-existing translation twice.
    part = Part()
    part.translate([10.0, 0.0, 0.0])
    for name in ("xz", "yz"):
        _close(getattr(part, name)().frame.position, [0, 0, 0])
