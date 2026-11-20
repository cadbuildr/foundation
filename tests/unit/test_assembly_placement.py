"""Placement poses (at=/rot_deg=), joint-less and loop-closing connections,
and hole wizards driven by an Anchor."""

import math

import numpy as np
import pytest

from cadbuildr.foundation import LoopClosureError, rotation_from_deg
from cadbuildr.foundation.dag_utils import show_dag
from cadbuildr.foundation.gen.models import (
    Anchor,
    Assembly,
    BoolParameter,
    ClearanceHole,
    Connection,
    CounterBoreHole,
    CounterSinkHole,
    Extrusion,
    Frame,
    Hole,
    Part,
    PartModifier,
    RevoluteJoint,
    RigidJoint,
    Sketch,
    Square,
    StringParameter,
    TappedHole,
)
from cadbuildr.foundation.math_utils import (
    quaternion_rotate_vector,
    tf_relative_to_frame,
)

FLIP_Q = [0.0, 1.0, 0.0, 0.0]


def _anchor(name, position, quaternion=(1.0, 0.0, 0.0, 0.0)):
    return Anchor(
        frame=Frame(
            top_frame=None,
            name=StringParameter(value=f"anchor_{name}_frame"),
            display=BoolParameter(value=False),
            position=list(position),
            quaternion=list(quaternion),
        ),
        name=StringParameter(value=name),
    )


def _block(size=20.0, height=10.0):
    part = Part()
    sketch = Sketch(part.xy())
    part.add_operation(
        Extrusion(Square.from_center_and_side(sketch.origin, size), height)
    )
    part.add_anchor(_anchor("top", [0, 0, height]))
    part.add_anchor(_anchor("probe", [10, 0, 0]))
    return part


def _world_point(anchor, assembly):
    t, _ = tf_relative_to_frame(anchor.frame, assembly.frame)
    return np.array(t)


def _world_axes(frame, ancestor=None):
    _, q = tf_relative_to_frame(frame, ancestor)
    return [
        np.array(quaternion_rotate_vector(q, v))
        for v in ([1, 0, 0], [0, 1, 0], [0, 0, 1])
    ]


def _nodes(dag, type_name):
    type_id = dag["serializableNodes"][type_name]
    return {k: n for k, n in dag["DAG"].items() if n["type"] == type_id}


# --------------------------------------------------------------------------- #
# 1. Placement convenience
# --------------------------------------------------------------------------- #


def test_add_component_at_translates():
    part = _block()
    asm = Assembly()
    asm.add_component(part, at=(1, 2, 3))
    assert asm.components[0].frame.position == pytest.approx([1, 2, 3])
    assert _world_point(part.anchor("probe"), asm) == pytest.approx([11, 2, 3])


def test_add_component_rot_deg_scalar_is_degrees_about_z_then_at():
    part = _block()
    asm = Assembly()
    asm.add_component(part, at=(1, 2, 3), rot_deg=90)
    # probe (10, 0, 0) rotated 90° about Z about the part origin -> (0, 10, 0),
    # then moved by at.
    assert _world_point(part.anchor("probe"), asm) == pytest.approx(
        [1, 12, 3], abs=1e-9
    )


def test_add_component_rot_deg_xyz_fixed_axes_order():
    part = _block()
    asm = Assembly()
    # X by 90 first: probe on +X is unchanged; then Y by 90: +X -> -Z;
    # then Z by 90: -Z unchanged.
    asm.add_component(part, rot_deg=(90, 90, 90))
    assert _world_point(part.anchor("probe"), asm) == pytest.approx(
        [0, 0, -10], abs=1e-9
    )
    # The anchor "top" (+Z axis of the part) after X90 -> -Y, Y90 -> -Y, Z90 -> +X.
    _, _, z_axis = _world_axes(part.anchor("top").frame, asm.frame)
    assert z_axis == pytest.approx([1, 0, 0], abs=1e-9)


def test_rotation_from_deg_matches_radian_axis_angle():
    q = rotation_from_deg(30)
    assert q == pytest.approx(
        [math.cos(math.radians(15)), 0, 0, math.sin(math.radians(15))]
    )
    with pytest.raises(ValueError, match="rot_deg"):
        rotation_from_deg((1, 2))


def test_add_component_pose_and_tf_are_exclusive():
    asm = Assembly()
    with pytest.raises(TypeError, match="either tf= or at="):
        asm.add_component(_block(), tf={"translation": [1, 0, 0]}, at=(1, 0, 0))


def test_add_component_tf_still_supported():
    part = _block()
    asm = Assembly()
    asm.add_component(part, {"translation": [5, 0, 0]})
    assert _world_point(part.anchor("probe"), asm) == pytest.approx([15, 0, 0])


def test_posed_component_stays_live():
    part = _block()
    asm = Assembly()
    asm.add_component(part, at=(0, 0, 50), rot_deg=45)
    before = len(_nodes(show_dag(asm), "Extrusion"))
    sketch = Sketch(part.xy())
    part.add_operation(
        Extrusion(Square.from_center_and_side(sketch.origin, 2), 3, cut=True)
    )
    assert len(_nodes(show_dag(asm), "Extrusion")) == before + 1


def test_ground_at_pose_places_anchor_there():
    part = _block()
    asm = Assembly()
    asm.ground(part.anchor("top"), at=(100, 0, 0), rot_deg=(0, 0, 90))
    t, q = tf_relative_to_frame(part.anchor("top").frame, asm.frame)
    assert t == pytest.approx([100, 0, 0], abs=1e-9)
    assert q == pytest.approx(rotation_from_deg(90), abs=1e-9)
    # Part origin sits 10 mm below the top anchor (anchor Z aligned, not flipped).
    assert asm.components[0].frame.position == pytest.approx([100, 0, -10], abs=1e-9)


def test_ground_default_still_origin():
    part = _block()
    asm = Assembly()
    asm.ground(part.anchor("top"))
    assert asm.components[0].frame.position == pytest.approx([0, 0, -10])


# --------------------------------------------------------------------------- #
# 2. Joint-less and loop-closing connections
# --------------------------------------------------------------------------- #


def _leg(name):
    """A 10 mm wide post; ``face`` anchor on its +X side at height 50."""
    part = _block(size=10.0, height=100.0)
    part.name = StringParameter(value=name)
    part.add_anchor(
        _anchor(
            "face_px", [5, 0, 50], [math.cos(math.pi / 4), 0, math.sin(math.pi / 4), 0]
        )
    )
    part.add_anchor(
        _anchor(
            "face_nx",
            [-5, 0, 50],
            [math.cos(math.pi / 4), 0, -math.sin(math.pi / 4), 0],
        )
    )
    return part


def _rail(length):
    """A rail along +X with end anchors pointing outward along its axis."""
    part = Part()
    part.name = StringParameter(value="rail")
    sketch = Sketch(part.yz())
    part.add_operation(Extrusion(Square.from_center_and_side(sketch.origin, 8), length))
    # end_a at x=0 facing -X, end_b at x=length facing +X.
    part.add_anchor(
        _anchor(
            "end_a", [0, 0, 0], [math.cos(math.pi / 4), 0, -math.sin(math.pi / 4), 0]
        )
    )
    part.add_anchor(
        _anchor(
            "end_b",
            [length, 0, 0],
            [math.cos(math.pi / 4), 0, math.sin(math.pi / 4), 0],
        )
    )
    return part


def _legs_and_rail(rail_length, gap=200.0):
    left, right = _leg("left"), _leg("right")
    rail = _rail(rail_length)
    asm = Assembly()
    asm.add_component(left)
    asm.add_component(right, at=(gap + 10.0, 0, 0))
    asm.add_joint(
        RigidJoint(
            parent_anchor=left.anchor("face_px"), child_anchor=rail.anchor("end_a")
        )
    )
    return asm, left, right, rail


def test_jointless_connection_only_applies_modifiers():
    plate = _block()
    asm = Assembly()
    asm.add_component(plate)
    top = plate.anchor("top")
    ops = len(plate.operations)
    assert asm.add_connection(
        Connection(modifiers=[PartModifier(anchor=top, operations=[Hole(top, 1.5, 4)])])
    )
    assert len(plate.operations) == ops + 1
    assert asm.joints == []
    assert len(asm.components) == 1


def test_loop_closure_passes_when_anchors_meet():
    asm, left, right, rail = _legs_and_rail(rail_length=200.0)
    joints_before = len(asm.joints)
    ops_before = len(right.operations)
    far = right.anchor("face_nx")
    mortise = Hole(far, 3, 5)
    asm.add_connection(
        Connection(
            name=StringParameter(value="far_mortise"),
            joint=RigidJoint(parent_anchor=far, child_anchor=rail.anchor("end_b")),
            modifiers=[PartModifier(anchor=far, operations=[mortise])],
        )
    )
    # Nothing re-placed, no joint recorded, the cut landed on the right leg.
    assert len(asm.joints) == joints_before
    assert len(asm.components) == 3
    assert len(right.operations) == ops_before + 1


def test_loop_closure_fails_with_clear_error_and_leaves_parts_untouched():
    asm, left, right, rail = _legs_and_rail(rail_length=199.0)  # 1 mm short
    far = right.anchor("face_nx")
    ops = len(right.operations)
    with pytest.raises(LoopClosureError, match=r"far_mortise.*off by 1\.000 mm"):
        asm.add_connection(
            Connection(
                name=StringParameter(value="far_mortise"),
                joint=RigidJoint(parent_anchor=far, child_anchor=rail.anchor("end_b")),
                modifiers=[PartModifier(anchor=far, operations=[Hole(far, 3, 5)])],
            )
        )
    assert len(right.operations) == ops


def test_loop_closure_tolerance_is_configurable():
    asm, left, right, rail = _legs_and_rail(rail_length=199.0)
    asm.add_connection(
        Connection(
            joint=RigidJoint(
                parent_anchor=right.anchor("face_nx"), child_anchor=rail.anchor("end_b")
            )
        ),
        pos_tol=1.5,
    )


def test_loop_closure_reports_orientation_error():
    asm, left, right, rail = _legs_and_rail(rail_length=200.0)
    tilted = right.anchor("face_nx").rotated(
        math.radians(2), axis=[1, 0, 0], name="tilt"
    )
    with pytest.raises(LoopClosureError, match=r"2\.000°"):
        asm.add_connection(
            Connection(
                joint=RigidJoint(
                    parent_anchor=tilted, child_anchor=rail.anchor("end_b")
                )
            )
        )


def test_revolute_loop_closure_ignores_twist_but_not_offset():
    asm, left, right, rail = _legs_and_rail(rail_length=200.0)
    spun = right.anchor("face_nx").rotated(math.radians(37), name="spun")
    asm.add_connection(
        Connection(
            joint=RevoluteJoint(parent_anchor=spun, child_anchor=rail.anchor("end_b"))
        )
    )
    with pytest.raises(LoopClosureError):
        asm.add_connection(
            Connection(
                joint=RigidJoint(parent_anchor=spun, child_anchor=rail.anchor("end_b"))
            )
        )
    lifted = right.anchor("face_nx").offset([0, 0.5, 0], name="lifted")
    with pytest.raises(LoopClosureError, match="0.500 mm"):
        asm.add_connection(
            Connection(
                joint=RevoluteJoint(
                    parent_anchor=lifted, child_anchor=rail.anchor("end_b")
                )
            )
        )


def test_closure_with_unplaced_parent_asks_to_swap():
    asm, left, right, rail = _legs_and_rail(rail_length=200.0)
    stray = _leg("stray")
    with pytest.raises(ValueError, match="Swap parent_anchor and child_anchor"):
        asm.add_connection(
            Connection(
                joint=RigidJoint(
                    parent_anchor=stray.anchor("face_nx"),
                    child_anchor=rail.anchor("end_b"),
                )
            )
        )


def test_add_joint_on_placed_child_points_at_add_connection():
    asm, left, right, rail = _legs_and_rail(rail_length=200.0)
    with pytest.raises(ValueError, match="add_connection"):
        asm.add_joint(
            RigidJoint(
                parent_anchor=right.anchor("face_nx"), child_anchor=rail.anchor("end_b")
            )
        )


# --------------------------------------------------------------------------- #
# 3. Hole wizards driven by an Anchor
# --------------------------------------------------------------------------- #


def _hole_extrusion(dag, sketch_plane_name):
    """The cut Extrusion whose sketch sits on the plane named ``sketch_plane_name``."""
    strings = {
        k: n["params"].get("value") for k, n in _nodes(dag, "StringParameter").items()
    }
    planes = {
        k
        for k, n in _nodes(dag, "Plane").items()
        if strings.get(n["deps"]["name"]) == sketch_plane_name
    }
    sketches = {
        k for k, n in _nodes(dag, "Sketch").items() if n["deps"]["plane"] in planes
    }
    return [
        n for n in _nodes(dag, "Extrusion").values() if n["deps"]["sketch"] in sketches
    ]


def test_hole_on_anchor_drills_along_anchor_minus_z():
    part = _block(height=10.0)
    side = part.add_anchor(
        _anchor(
            "side", [10, 3, 5], [math.cos(math.pi / 4), 0, math.sin(math.pi / 4), 0]
        )
    )  # +Z of the anchor points out along part +X
    hole = Hole(side, radius=2, depth=6)
    part.add_operation(hole)

    plane = hole.point.sketch.plane
    assert plane.frame.top_frame is side.frame
    origin, _ = tf_relative_to_frame(plane.frame, part.frame)
    _, _, axis = _world_axes(plane.frame, part.frame)
    assert origin == pytest.approx([10, 3, 5], abs=1e-9)
    assert axis == pytest.approx([-1, 0, 0], abs=1e-9)  # into the part

    dag = show_dag(part)
    (extrusion,) = _hole_extrusion(dag, "hole_side")
    floats = {k: n["params"]["value"] for k, n in _nodes(dag, "FloatParameter").items()}
    bools = {k: n["params"]["value"] for k, n in _nodes(dag, "BoolParameter").items()}
    assert bools[extrusion["deps"]["cut"]] is True
    assert floats[extrusion["deps"]["start"]] == 0.0
    assert floats[extrusion["deps"]["end"]] == 6.0
    # The DAG frame chain: hole frame (flip) -> anchor frame -> part frame.
    frames = _nodes(dag, "Frame")
    plane_node = next(
        n
        for n in _nodes(dag, "Plane").values()
        if frames[n["deps"]["frame"]]["params"]["quaternion"] == FLIP_Q
    )
    hole_frame = frames[plane_node["deps"]["frame"]]
    anchor_frame = frames[hole_frame["deps"]["top_frame"]]
    assert anchor_frame["params"]["position"] == [10, 3, 5]


def test_hole_anchor_keyword_and_point_slot():
    part = _block()
    top = part.anchor("top")
    a = Hole(anchor=top, radius=1, depth=2)
    b = Hole(point=top, radius=1, depth=2)
    assert a.point.sketch.plane.frame.top_frame is top.frame
    assert b.point.sketch.plane.frame.top_frame is top.frame
    with pytest.raises(TypeError, match="anchor="):
        Hole(top, 1, 2, anchor=top)


def test_hole_on_placed_rotated_part_follows_world_pose():
    part = _block(height=10.0)
    asm = Assembly()
    asm.add_component(part, at=(0, 0, 100), rot_deg=(180, 0, 0))  # upside down
    hole = Hole(part.anchor("top"), 2, 6)
    part.add_operation(hole)
    origin, _ = tf_relative_to_frame(hole.point.sketch.plane.frame, asm.frame)
    _, _, axis = _world_axes(hole.point.sketch.plane.frame, asm.frame)
    assert origin == pytest.approx([0, 0, 90], abs=1e-9)
    assert axis == pytest.approx(
        [0, 0, 1], abs=1e-9
    )  # drills up into the flipped block
    assert len(_hole_extrusion(show_dag(asm), "hole_top")) == 1


@pytest.mark.parametrize(
    "make, polygon_lines",
    [
        (
            lambda a: CounterSinkHole(
                a, radius=2, depth=8, csink_radius=4, csink_angle_deg=90
            ),
            5,
        ),
        (
            lambda a: CounterBoreHole(
                a, radius=2, depth=8, cbore_radius=4, cbore_depth=3
            ),
            6,
        ),
    ],
)
def test_lathed_holes_on_anchor_revolve_about_anchor_z(make, polygon_lines):
    part = _block(height=10.0)
    hole = make(part.anchor("top"))
    part.add_operation(hole)
    # The revolve axis line (local Y of the revolve sketch) maps to the anchor -Z.
    axis_sketch = hole.axis_line.p1.sketch
    _, y_axis, _ = _world_axes(axis_sketch.plane.frame, part.frame)
    origin, _ = tf_relative_to_frame(axis_sketch.plane.frame, part.frame)
    assert y_axis == pytest.approx([0, 0, -1], abs=1e-9)
    assert origin == pytest.approx([0, 0, 10], abs=1e-9)
    dag = show_dag(part)
    assert any(
        len(p["deps"]["lines"]) == polygon_lines
        for p in _nodes(dag, "Polygon").values()
    )
    assert _nodes(dag, "Lathe")


def test_tapped_and_clearance_holes_accept_anchor():
    part = _block(height=10.0)
    top = part.anchor("top")
    part.add_operation(TappedHole(top, thread_size=5, depth=8))
    part.add_operation(ClearanceHole(anchor=top, size=3, depth=8))
    dag = show_dag(part)
    assert len(_hole_extrusion(dag, "hole_top")) == 2
    assert "Hole" not in {
        name
        for name, tid in dag["serializableNodes"].items()
        if any(n["type"] == tid for n in dag["DAG"].values())
    }


def test_anchor_hole_as_part_modifier_in_connection():
    plate = _block(height=10.0)
    pin = _block(size=4.0, height=8.0)
    pin.add_anchor(_anchor("tip", [0, 0, 0], FLIP_Q))
    asm = Assembly()
    asm.add_component(plate)
    top = plate.anchor("top")
    asm.add_connection(
        Connection(
            joint=RigidJoint(parent_anchor=top, child_anchor=pin.anchor("tip")),
            modifiers=[
                PartModifier(
                    anchor=top, operations=[CounterSinkHole(top, 2.2, 6, 4, 90)]
                )
            ],
        )
    )
    assert asm.components[-1].frame.position == pytest.approx([0, 0, 10])
    assert _nodes(show_dag(asm), "Lathe")
