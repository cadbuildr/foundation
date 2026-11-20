"""make_anchor from directions, anchor patterns, degree variants, naming."""

import math

import numpy as np
import pytest

from cadbuildr.foundation import (
    Assembly,
    Extrusion,
    Part,
    RigidJoint,
    Sketch,
    Square,
    TFHelper,
    make_anchor,
    show_dag,
)
from cadbuildr.foundation.gen.models import BoolParameter
from cadbuildr.foundation.math_utils import (
    axis_angle_to_quaternion,
    default_x_for_z,
    quaternion_from_directions,
    quaternion_to_axes,
    tf_relative_to_frame,
)


def _box(size=10.0):
    part = Part()
    sketch = Sketch(part.xy())
    part.add_operation(
        Extrusion(Square.from_center_and_side(sketch.origin, size), size)
    )
    return part


def _axes(q):
    return [np.asarray(a) for a in quaternion_to_axes(q)]


def _pose(anchor, part):
    """(position, x, y, z) of ``anchor`` in ``part`` coordinates."""
    t, q = tf_relative_to_frame(anchor.frame, part.frame)
    return (np.asarray(t), *_axes(q))


def _close(a, b, tol=1e-9):
    return np.allclose(np.asarray(a, dtype=float), np.asarray(b, dtype=float), atol=tol)


# --------------------------------------------------------------------------- #
# make_anchor(z_axis=, x_axis=)
# --------------------------------------------------------------------------- #


def test_make_anchor_z_and_x_exact():
    a = make_anchor("side", (1, 2, 3), z_axis=(1, 0, 0), x_axis=(0, 1, 0))
    x, y, z = _axes(a.frame.quaternion)
    assert _close(z, [1, 0, 0]) and _close(x, [0, 1, 0]) and _close(y, [0, 0, 1])
    assert a.frame.position == [1.0, 2.0, 3.0]


def test_make_anchor_x_is_projected_off_z():
    a = make_anchor("tilted", z_axis=(0, 0, 2), x_axis=(1, 0, 5))
    x, y, z = _axes(a.frame.quaternion)
    assert _close(z, [0, 0, 1]) and _close(x, [1, 0, 0]) and _close(y, [0, 1, 0])


def test_make_anchor_non_axis_aligned_is_orthonormal():
    a = make_anchor("skew", z_axis=(1, 1, 1), x_axis=(1, -1, 0.3))
    x, y, z = _axes(a.frame.quaternion)
    assert _close(z, np.array([1, 1, 1]) / math.sqrt(3))
    assert _close(np.cross(x, y), z)
    assert abs(np.dot(x, z)) < 1e-9 and abs(np.linalg.norm(x) - 1) < 1e-9
    # x stays in the plane spanned by z and the hint
    hint = np.array([1, -1, 0.3])
    assert abs(np.dot(np.cross(z, hint), x)) < 1e-9
    assert np.dot(x, hint) > 0


@pytest.mark.parametrize(
    "z, expected_x",
    [
        ((0, 0, 1), (1, 0, 0)),  # identity
        ((0, 0, -1), (1, 0, 0)),  # same as z_down
        ((1, 0, 0), (0, 0, -1)),  # shortest arc about +Y
        ((0, 1, 0), (1, 0, 0)),  # shortest arc about -X keeps X
        ((-1, 0, 0), (0, 0, 1)),
    ],
)
def test_default_x_rule(z, expected_x):
    assert _close(default_x_for_z(z), expected_x)
    x, _, zz = _axes(make_anchor("a", z_axis=z).frame.quaternion)
    assert _close(zz, np.asarray(z) / np.linalg.norm(z)) and _close(x, expected_x)


def test_z_axis_minus_z_matches_z_down():
    a = make_anchor("a", z_axis=(0, 0, -1))
    b = make_anchor("b", z_down=True)
    assert _close(_axes(a.frame.quaternion), _axes(b.frame.quaternion))


def test_quaternion_from_directions_matches_axis_angle():
    q = quaternion_from_directions((1, 0, 0))
    assert _close(q, axis_angle_to_quaternion([0, 1, 0], math.pi / 2))


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"z_axis": (0, 0, 0)}, "non-zero"),
        ({"z_axis": (0, 0, 1), "x_axis": (0, 0, 0)}, "non-zero"),
        ({"z_axis": (0, 0, 1), "x_axis": (0, 0, -3)}, "parallel"),
        ({"z_axis": (0, 1)}, "3 components"),
        ({"x_axis": (1, 0, 0)}, "needs z_axis"),
        ({"z_axis": (0, 0, 1), "z_down": True}, "not both"),
        ({"z_axis": (0, 0, 1), "quaternion": (1, 0, 0, 0)}, "not both"),
    ],
)
def test_make_anchor_direction_errors(kwargs, match):
    with pytest.raises(ValueError, match=match):
        make_anchor("bad", **kwargs)


def test_make_anchor_positional_quaternion_still_works():
    q = axis_angle_to_quaternion([0, 1, 0], math.pi / 2)
    a = make_anchor("legacy", (0, 0, 5), q)
    assert a.frame.quaternion == [float(c) for c in q]


# --------------------------------------------------------------------------- #
# Degree variants (radians remain the default)
# --------------------------------------------------------------------------- #


def test_rotate_units_radians_and_deg_variants():
    p_rad, p_deg = Part(), Part()
    p_rad.rotate(math.pi / 2, [0, 0, 1])
    p_deg.rotate_deg(90, [0, 0, 1])
    assert _close(p_rad.frame.quaternion, p_deg.frame.quaternion)
    assert _close(_axes(p_deg.frame.quaternion)[0], [0, 1, 0])

    asm = Assembly()
    asm.rotate_deg(180, [1, 0, 0])
    assert _close(_axes(asm.frame.quaternion)[2], [0, 0, -1])

    tf_rad = TFHelper().rotate([0, 0, 1], math.pi / 2).get_tf()["quaternion"]
    tf_deg = TFHelper().rotate_deg([0, 0, 1], 90).get_tf()["quaternion"]
    assert _close(tf_rad, tf_deg) and _close(tf_rad, p_rad.frame.quaternion)


def test_anchor_rotated_deg():
    part = _box()
    base = part.add_anchor(make_anchor("top", (0, 0, 10)))
    a = base.rotated_deg(90)
    b = base.rotated(math.pi / 2)
    assert _close(a.frame.quaternion, b.frame.quaternion)
    assert a.name.value == "top_rotated" and b.name.value == "top_rotated_2"


# --------------------------------------------------------------------------- #
# Patterns
# --------------------------------------------------------------------------- #


def test_linear_pattern_positions_names_orientation():
    part = _box()
    base = part.add_anchor(make_anchor("row", (5, 0, 10), z_axis=(0, 0, 1)))
    row = base.linear_pattern(4, 2.5, direction=(0, 2, 0))
    assert [a.name.value for a in row] == ["row_0", "row_1", "row_2", "row_3"]
    for i, a in enumerate(row):
        t, x, _, z = _pose(a, part)
        assert (
            _close(t, [5, 2.5 * i, 10])
            and _close(x, [1, 0, 0])
            and _close(z, [0, 0, 1])
        )
        assert a.frame.top_frame is base.frame


def test_linear_pattern_direction_is_local():
    part = _box()
    base = part.add_anchor(make_anchor("side", (0, 0, 0), z_axis=(1, 0, 0)))
    row = base.linear_pattern(3, 10.0)  # local +X == part -Z here
    t, *_ = _pose(row[2], part)
    assert _close(t, [0, 0, -20])


def test_polar_pattern_bolt_circle():
    part = _box()
    hub = part.add_anchor(make_anchor("hub", (0, 0, 10)))
    bolts = hub.polar_pattern(6, radius=40.0)
    assert len(bolts) == 6 and bolts[5].name.value == "hub_5"
    for i, a in enumerate(bolts):
        theta = i * math.pi / 3
        t, x, _, z = _pose(a, part)
        radial = [math.cos(theta), math.sin(theta), 0]
        assert _close(t, [40 * radial[0], 40 * radial[1], 10])
        assert _close(x, radial) and _close(z, [0, 0, 1])


def test_polar_pattern_partial_span_hits_both_ends_and_deg_form():
    part = _box()
    hub = part.add_anchor(make_anchor("hub", (0, 0, 0)))
    arc = hub.polar_pattern(3, radius=10.0, angle_deg=90, name="arc")
    assert [a.name.value for a in arc] == ["hub_arc_0", "hub_arc_1", "hub_arc_2"]
    assert _close(_pose(arc[0], part)[0], [10, 0, 0])
    assert _close(_pose(arc[1], part)[0], [10 / math.sqrt(2), 10 / math.sqrt(2), 0])
    assert _close(_pose(arc[2], part)[0], [0, 10, 0])
    with pytest.raises(ValueError, match="not both"):
        hub.polar_pattern(3, angle=1.0, angle_deg=90)


def test_polar_pattern_without_radius_clocks_about_z():
    part = _box()
    base = part.add_anchor(make_anchor("c", (1, 2, 3), z_axis=(0, 1, 0)))
    clocks = base.polar_pattern(4, start_angle_deg=45)
    for i, a in enumerate(clocks):
        t, x, _, z = _pose(a, part)
        assert _close(t, [1, 2, 3]) and _close(z, [0, 1, 0])
        # base X is default_x_for_z(+Y) = +X; rotated about +Y by 45° + i*90°
        theta = math.radians(45 + 90 * i)
        assert _close(x, [math.cos(theta), 0, -math.sin(theta)])


def test_along_path_spacing_and_tangent_x():
    part = _box()
    start = part.add_anchor(make_anchor("start", (0, 0, 0)))
    path = [(0, 0, 0), (100, 0, 0), (100, 50, 0)]  # length 150
    beads = start.along_path(path, 4)  # spacing 50
    assert [a.name.value for a in beads] == ["start_0", "start_1", "start_2", "start_3"]
    expected = [
        ([0, 0, 0], [1, 0, 0]),
        ([50, 0, 0], [1, 0, 0]),
        ([100, 0, 0], [0, 1, 0]),  # at the corner: outgoing tangent
        ([100, 50, 0], [0, 1, 0]),
    ]
    for a, (pos, tangent) in zip(beads, expected):
        t, x, _, z = _pose(a, part)
        assert _close(t, pos) and _close(x, tangent) and _close(z, [0, 0, 1])


def test_along_path_closed_loop_and_vertical_fallback():
    part = _box()
    start = part.add_anchor(make_anchor("loop", (0, 0, 0)))
    square = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    ring = start.along_path(square, 4)
    assert [list(_pose(a, part)[0]) for a in ring] == [
        [0, 0, 0],
        [10, 0, 0],
        [10, 10, 0],
        [0, 10, 0],
    ]
    up = start.along_path([(0, 0, 0), (0, 0, 30)], 2, name="riser")
    t, x, _, z = _pose(up[1], part)
    assert _close(t, [0, 0, 30]) and _close(x, [0, 0, 1]) and _close(z, [1, 0, 0])


@pytest.mark.parametrize(
    "call, match",
    [
        (lambda a: a.linear_pattern(0, 1.0), "positive integer"),
        (lambda a: a.linear_pattern(2, 1.0, direction=(0, 0, 0)), "non-zero"),
        (lambda a: a.polar_pattern(2.5), "positive integer"),
        (lambda a: a.along_path([(0, 0, 0), (0, 0, 0)], 3), "two distinct"),
    ],
)
def test_pattern_errors(call, match):
    anchor = _box().add_anchor(make_anchor("a"))
    with pytest.raises(ValueError, match=match):
        call(anchor)


def test_pattern_anchors_register_and_serialise():
    part = _box()
    hub = part.add_anchor(make_anchor("hub", (0, 0, 10)))
    bolts = part.add_anchors(hub.polar_pattern(3, radius=4.0))
    assert part.anchor("hub_2") is bolts[2]
    dag = show_dag(part)
    assert dag["rootNodeId"]


def test_pattern_anchor_works_in_a_joint():
    parent, child = _box(), _box(4.0)
    hub = parent.add_anchor(make_anchor("hub", (0, 0, 10)))
    seat = hub.polar_pattern(4, radius=3.0)[1]  # at (0, 3, 10), X=+Y
    pin = child.add_anchor(make_anchor("pin", (0, 0, 0), z_down=True))
    asm = Assembly()
    asm.add_component(parent)
    asm.add_joint(
        RigidJoint(
            parent_anchor=seat, child_anchor=pin, flip=BoolParameter(value=False)
        )
    )
    t, _ = tf_relative_to_frame(pin.frame, asm.frame)
    assert _close(t, [0, 3, 10])


# --------------------------------------------------------------------------- #
# Naming / collisions
# --------------------------------------------------------------------------- #


def test_registered_duplicate_still_raises():
    part = _box()
    part.add_anchor(make_anchor("top"))
    with pytest.raises(ValueError, match="already exists"):
        part.add_anchor(make_anchor("top"))


def test_repeated_derivation_auto_suffixes():
    part = _box()
    top = part.add_anchor(make_anchor("top", (0, 0, 10)))
    names = [top.offset([0, 0, i], name="seat").name.value for i in range(3)]
    assert names == ["top_seat", "top_seat_2", "top_seat_3"]


def test_second_pattern_on_same_base_gets_a_fresh_block():
    part = _box()
    hub = part.add_anchor(make_anchor("hub"))
    first = hub.polar_pattern(3, radius=1.0)
    second = hub.polar_pattern(2, radius=2.0)
    assert [a.name.value for a in first] == ["hub_0", "hub_1", "hub_2"]
    assert [a.name.value for a in second] == ["hub_2_0", "hub_2_1"]
    part.add_anchors(first + second)  # all unique: registers cleanly


def test_derived_name_skips_registered_names_and_vice_versa():
    part = _box()
    top = part.add_anchor(make_anchor("top"))
    part.add_anchor(make_anchor("top_offset"))
    assert top.offset([0, 0, 1]).name.value == "top_offset_2"
    top.offset([0, 0, 2], name="clamp")
    with pytest.raises(ValueError, match="derived anchor"):
        part.add_anchor(make_anchor("top_clamp"))


def test_registering_a_derived_anchor_is_allowed_once():
    part = _box()
    top = part.add_anchor(make_anchor("top"))
    seat = top.offset([0, 0, 1], name="seat")
    assert part.add_anchor(seat) is seat
    assert part.add_anchor(seat) is seat  # idempotent for the same object


def test_unowned_base_namespace_merges_on_registration():
    part = _box()
    loose = make_anchor("loose")
    derived = loose.linear_pattern(2, 1.0)
    assert [a.name.value for a in derived] == ["loose_0", "loose_1"]
    part.add_anchor(loose)
    part.add_anchors(derived)
    assert part.anchor("loose_1") is derived[1]
    # names derived before registration stay reserved afterwards
    assert loose.linear_pattern(1, 1.0)[0].name.value == "loose_2_0"


def test_same_names_on_different_owners_do_not_interfere():
    a, b = _box(), _box()
    ta = a.add_anchor(make_anchor("top"))
    tb = b.add_anchor(make_anchor("top"))
    assert (
        ta.offset([0, 0, 1]).name.value
        == tb.offset([0, 0, 1]).name.value
        == "top_offset"
    )


def test_chained_derivation_like_tube_tee_never_collides():
    """stdlib tube_tee derives radial -> seat chains; two tees at the same
    station used to need hand-made unique labels."""
    tube = _box()
    axis = tube.add_anchor(make_anchor("axis"))

    def seat():
        return (
            axis.rotated(0.0, name="tee_spin")
            .offset([5.0, 0.0, 10.0], name="tee_pt")
            .rotated(math.pi / 2, axis=[0, 1, 0], name="tee")
            .offset([0.0, 0.0, -1.0], name="tee_seat")
        )

    s1, s2 = seat(), seat()
    assert s1.name.value != s2.name.value
    tube.add_anchors([s1, s2])
