"""Interference check between assembly components (Assembly.check_interference)."""

import math

import numpy as np
import pytest

from cadbuildr.foundation import (
    OBB,
    InterferenceError,
    anchor_plane,
    estimate_part_extents,
    make_anchor,
    obb_intersects,
    obb_penetration,
    set_part_extents,
)
from cadbuildr.foundation.gen.models import (
    Assembly,
    Axis,
    Circle,
    Connection,
    Extrusion,
    ExtrudeEndCondition,
    Lathe,
    Line,
    Part,
    PartModifier,
    Point,
    RectangleFromCenterAndSides,
    RigidJoint,
    Sketch,
    Sphere,
    Square,
    Text,
)


def block(size=10.0, height=10.0):
    """size × size × height, centred on the origin in XY, z in [0, height]."""
    part = Part()
    sketch = Sketch(part.xy())
    part.add_operation(
        Extrusion(Square.from_center_and_side(sketch.origin, size), height)
    )
    return part


def bar(length, width, height):
    """length (X) × width (Y) × height (Z), centred in XY, z in [0, height]."""
    part = Part()
    sketch = Sketch(part.xy())
    rect = RectangleFromCenterAndSides(sketch.origin, length, width, sketch)
    part.add_operation(Extrusion(rect, height))
    return part


def overlaps(results):
    return [r for r in results if r.status == "overlap"]


# --------------------------------------------------------------------------- #
# Two boxes: overlapping / touching / apart
# --------------------------------------------------------------------------- #


def test_overlapping_boxes_reported_with_depth_and_volume():
    asm = Assembly()
    asm.add_component(block())
    asm.add_component(block(), at=(6.0, 0.0, 0.0))
    [hit] = asm.check_interference()
    assert hit.status == "overlap"
    assert (hit.path_a, hit.path_b) == ("part_0", "part_1")
    assert hit.depth == pytest.approx(4.0)
    assert hit.volume == pytest.approx(4.0 * 10.0 * 10.0)


def test_touching_boxes_not_reported():
    asm = Assembly()
    asm.add_component(block())
    asm.add_component(block(), at=(10.0, 0.0, 0.0))
    asm.add_component(block(), at=(0.0, 0.0, 10.0))  # stacked face to face
    assert asm.check_interference() == []


def test_apart_boxes_not_reported():
    asm = Assembly()
    asm.add_component(block())
    asm.add_component(block(), at=(25.0, 3.0, -1.0))
    assert asm.check_interference() == []


def test_tolerance_accepts_shallow_overlap():
    asm = Assembly()
    asm.add_component(block())
    asm.add_component(block(), at=(9.8, 0.0, 0.0))
    assert len(asm.check_interference()) == 1
    assert asm.check_interference(tolerance=0.25) == []


def test_strict_raises_with_paths():
    asm = Assembly()
    asm.add_component(block())
    asm.add_component(block(), at=(5.0, 0.0, 0.0))
    with pytest.raises(InterferenceError) as exc:
        asm.check_interference(strict=True)
    assert "part_0 <-> part_1" in str(exc.value)
    assert exc.value.interferences[0].depth == pytest.approx(5.0)


# --------------------------------------------------------------------------- #
# Rotated parts need OBB, not AABB
# --------------------------------------------------------------------------- #


def test_rotated_bar_clear_of_block_inside_its_aabb():
    # A 100 × 4 bar rotated 45° about Z has a ~73 × 73 world AABB. A block in
    # the empty corner of that AABB touches the AABB but not the bar.
    asm = Assembly()
    asm.add_component(bar(100.0, 4.0, 5.0), rot_deg=45)
    asm.add_component(block(10.0, 5.0), at=(25.0, -25.0, 0.0))
    assert asm.check_interference() == []

    # Sanity: the axis-aligned bounding boxes do overlap.
    rotated = estimate_part_extents(asm.components[0]).boxes[0]
    rot = OBB(rotated.center, np.eye(3), rotated.half).transformed(
        np.array(
            [
                [math.cos(math.pi / 4), -math.sin(math.pi / 4), 0],
                [math.sin(math.pi / 4), math.cos(math.pi / 4), 0],
                [0, 0, 1],
            ]
        ),
        [0, 0, 0],
    )
    world_aabb = OBB.from_points(rot.corners())
    other = OBB.from_bounds([20, -30, 0], [30, -20, 5])
    assert obb_penetration(world_aabb, other) > 0


def test_rotated_bar_hitting_block():
    asm = Assembly()
    asm.add_component(bar(100.0, 4.0, 5.0), rot_deg=45)
    asm.add_component(block(10.0, 5.0), at=(20.0, 20.0, 0.0))  # on the bar's diagonal
    [hit] = overlaps(asm.check_interference())
    assert hit.depth > 1.0


def test_rotated_about_x_with_tuple_rot_deg():
    # A tall post laid down along +Y by rotating -90° about X.
    asm = Assembly()
    asm.add_component(bar(4.0, 4.0, 50.0), rot_deg=(-90, 0, 0))
    asm.add_component(block(10.0, 10.0), at=(0.0, 30.0, -5.0))
    asm.add_component(block(10.0, 10.0), at=(0.0, -30.0, -5.0))  # behind it: clear
    [hit] = asm.check_interference()
    assert hit.path_b == "part_1"


def test_obb_intersects_margin_matches_woodworking_semantics():
    a = OBB.from_bounds([0, 0, 0], [10, 10, 10])
    touching = OBB.from_bounds([10, 0, 0], [20, 10, 10])
    assert obb_intersects(a, touching)  # closed boxes: contact counts
    assert not obb_intersects(a, touching, margin=0.05)
    assert obb_penetration(a, touching) == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# Intended contacts: joints, connections, allow-list
# --------------------------------------------------------------------------- #


def plate_and_pin():
    plate = block(30.0, 5.0)
    plate.add_anchor(make_anchor("mount", [0, 0, 5.0]))
    pin = Part()
    sketch = Sketch(pin.xy())
    pin.add_operation(Extrusion(Circle(sketch.origin, 2.0), 12.0))
    # Pin tip anchor 6 mm up the pin, facing down: half of it sinks into the plate.
    pin.add_anchor(make_anchor("tip", [0, 0, 6.0], z_down=True))
    return plate, pin


def test_jointed_pair_not_reported():
    plate, pin = plate_and_pin()
    asm = Assembly()
    asm.add_component(plate)
    asm.add_joint(
        RigidJoint(
            parent_anchor=plate.anchor("mount"),
            child_anchor=pin.anchor("tip"),
            flip=False,
        )
    )
    assert asm.check_interference() == []


def test_same_overlap_without_joint_is_reported():
    plate, pin = plate_and_pin()
    asm = Assembly()
    asm.add_component(plate)
    asm.add_component(pin, at=(0.0, 0.0, -1.0))
    [hit] = asm.check_interference()
    assert hit.status == "overlap"


def test_screw_in_its_drilled_hole_via_connection_not_reported():
    plate, pin = plate_and_pin()
    asm = Assembly()
    asm.add_component(plate)
    mount = plate.anchor("mount")
    sketch = Sketch(anchor_plane(mount))
    drill = Extrusion(Circle(sketch.origin, 2.1), 0.0, start=-5.0, cut=True)
    asm.add_connection(
        Connection(
            joint=RigidJoint(
                parent_anchor=mount, child_anchor=pin.anchor("tip"), flip=False
            ),
            modifiers=[PartModifier(anchor=mount, operations=[drill])],
        )
    )
    # The drill is a cut: it doesn't change the plate's outer bounds.
    assert len(estimate_part_extents(plate).boxes) == 1
    assert asm.check_interference() == []


def test_modifier_only_connection_allows_the_pair():
    a, b = block(), block()
    a.add_anchor(make_anchor("face", [5.0, 0, 5.0]))
    b.add_anchor(make_anchor("face", [-5.0, 0, 5.0]))
    asm = Assembly()
    asm.add_component(a)
    asm.add_component(b, at=(8.0, 0.0, 0.0))  # 2 mm overlap, e.g. a glued lap
    assert len(asm.check_interference()) == 1
    noop = Extrusion(
        Circle(Sketch(anchor_plane(a.anchor("face"))).origin, 1.0), 1.0, cut=True
    )
    asm.add_connection(
        Connection(
            modifiers=[
                PartModifier(anchor=a.anchor("face"), operations=[noop]),
                PartModifier(anchor=b.anchor("face"), operations=[]),
            ]
        )
    )
    assert asm.check_interference() == []


def test_loop_closing_connection_allows_the_pair():
    # Both parts placed by pose; a loop-closing rigid connection asserts the
    # anchors agree and must also mark the pair as an intended contact.
    a, b = block(), block()
    a.add_anchor(make_anchor("east", [5.0, 0, 5.0], z_axis=(1, 0, 0), x_axis=(0, 0, 1)))
    b.add_anchor(
        make_anchor("west", [-3.0, 0, 5.0], z_axis=(-1, 0, 0), x_axis=(0, 0, 1))
    )
    asm = Assembly()
    asm.add_component(a)
    asm.add_component(b, at=(8.0, 0.0, 0.0))
    assert len(asm.check_interference()) == 1
    asm.add_connection(
        Connection(
            joint=RigidJoint(
                parent_anchor=a.anchor("east"), child_anchor=b.anchor("west")
            )
        )
    )
    assert asm.joints == []  # loop closures are not appended to joints...
    assert asm.check_interference() == []  # ...but still count as intended


def test_ground_joint_does_not_allow_everything():
    asm = Assembly()
    a, b = block(), block()
    a.add_anchor(make_anchor("base", [0, 0, 0]))
    asm.ground(a.anchor("base"), at=(0, 0, 0), rot_deg=30)
    asm.add_component(b, at=(4.0, 0.0, 0.0))
    [hit] = asm.check_interference()
    assert {hit.path_a, hit.path_b} == {"part_0", "part_1"}


def test_allow_list_by_object_path_and_ignore():
    a, b, c = block(), block(), block()
    a.name.value = "base"
    asm = Assembly()
    asm.add_component(a)
    asm.add_component(b, at=(5.0, 0.0, 0.0))
    asm.add_component(c, at=(0.0, 5.0, 0.0))
    assert len(asm.check_interference()) == 3
    assert len(asm.check_interference(allow=[(a, b)])) == 2
    assert len(asm.check_interference(allow=[("base", "part_2")])) == 2
    assert asm.check_interference(allow=[a, (b, c)]) == []
    with pytest.raises(ValueError, match="no component at path"):
        asm.check_interference(allow=[("base", "nope")])


# --------------------------------------------------------------------------- #
# Woodworking-style mortise and tenon
# --------------------------------------------------------------------------- #


def test_mortise_and_tenon_not_reported():
    # Rail 100 (X) × 20 × 20 with a 15 mm tenon at +X; leg 20 × 20 × 200 (Z).
    # The tenon (cut from the rail's end by shoulder cuts) sits inside the
    # leg's mortise (a pocket cut by the connection's modifier).
    rail = bar(100.0, 20.0, 20.0)
    for y in (-7.5, 7.5):  # shoulder cuts leave a 10 mm-thick tenon at x > 35
        sketch = Sketch(rail.xy())
        shoulder = RectangleFromCenterAndSides(
            Point(sketch, 42.5, y), 15.0, 5.0, sketch
        )
        rail.add_operation(Extrusion(shoulder, 20.0, cut=True))
    rail.add_anchor(make_anchor("shoulder", [35.0, 0, 10.0], z_axis=(1, 0, 0)))

    leg = bar(20.0, 20.0, 200.0)
    leg.add_anchor(make_anchor("face", [-10.0, 0, 100.0], z_axis=(-1, 0, 0)))
    face = leg.anchor("face")
    pocket_sketch = Sketch(anchor_plane(face))
    mortise = Extrusion(
        RectangleFromCenterAndSides(pocket_sketch.origin, 5.0, 20.0, pocket_sketch),
        0.0,
        start=-15.5,
        cut=True,
    )

    asm = Assembly()
    asm.add_component(leg)
    asm.add_connection(
        Connection(
            joint=RigidJoint(parent_anchor=face, child_anchor=rail.anchor("shoulder")),
            modifiers=[PartModifier(anchor=face, operations=[mortise])],
        )
    )
    # The rail's bounding box runs 15 mm into the leg (same pose, no joint)...
    unjoined = Assembly()
    unjoined.add_component(bar(20.0, 20.0, 200.0))
    unjoined.add_component(bar(100.0, 20.0, 20.0), at=(-45.0, 0.0, 90.0))
    [hit] = unjoined.check_interference()
    assert hit.depth == pytest.approx(15.0)
    rail_root = asm.components[1]
    # (the mate rolls the rail 180° about its axis: origin at z=110, same box)
    np.testing.assert_allclose(rail_root.frame.position, [-45.0, 0.0, 110.0], atol=1e-9)
    # ...but it is the tenon in its mortise: not an interference.
    assert asm.check_interference() == []


# --------------------------------------------------------------------------- #
# Nested assemblies
# --------------------------------------------------------------------------- #


def test_nested_assembly_paths_and_transforms():
    sub = Assembly()
    sub.name.value = "drawer"
    sub.add_component(block(), at=(0.0, 0.0, 0.0))
    sub.add_component(block(), at=(20.0, 0.0, 0.0))

    top = Assembly()
    top.add_component(sub, at=(100.0, 0.0, 0.0))
    top.add_component(block(), at=(125.0, 0.0, 0.0))  # hits drawer's 2nd part only
    [hit] = top.check_interference()
    assert {hit.path_a, hit.path_b} == {"drawer/part_1", "part_1"}
    assert hit.depth == pytest.approx(5.0)

    # allow a whole sub-assembly against a part by path prefix
    assert top.check_interference(allow=[("drawer", "part_1")]) == []


def test_nested_assembly_rotated_and_late_component():
    sub = Assembly()
    sub.name.value = "arm"
    sub.add_component(bar(40.0, 4.0, 4.0), at=(20.0, 0.0, 0.0))

    top = Assembly()
    top.add_component(sub, rot_deg=90)  # the arm now points along +Y
    top.add_component(block(6.0, 4.0), at=(0.0, 30.0, 0.0))  # on the arm
    top.add_component(block(6.0, 4.0), at=(30.0, 0.0, 0.0))  # where it was
    [hit] = top.check_interference()
    assert {hit.path_a, hit.path_b} == {"arm/part_0", "part_1"}

    # A part added to the sub-assembly after it was placed is still checked.
    sub.add_component(block(6.0, 4.0), at=(-30.0, 0.0, 0.0))  # -> world (0, -30)
    top.add_component(block(6.0, 4.0), at=(0.0, -31.0, 0.0))
    paths = {frozenset((r.path_a, r.path_b)) for r in top.check_interference()}
    assert frozenset(("arm/part_1", "part_3")) in paths


def test_joint_inside_sub_assembly_is_respected():
    plate, pin = plate_and_pin()
    sub = Assembly()
    sub.add_component(plate)
    sub.add_joint(
        RigidJoint(
            parent_anchor=plate.anchor("mount"),
            child_anchor=pin.anchor("tip"),
            flip=False,
        )
    )
    top = Assembly()
    top.add_component(sub, at=(0.0, 0.0, 50.0))
    assert top.check_interference() == []


# --------------------------------------------------------------------------- #
# Extent estimation and unknowns
# --------------------------------------------------------------------------- #


def text_part():
    part = Part()
    sketch = Sketch(part.xy())
    part.add_operation(Extrusion(Text(sketch, "hi", 10.0), 2.0))
    return part


def test_unknown_extents_reported_as_unknown_not_guessed():
    asm = Assembly()
    asm.add_component(text_part())
    asm.add_component(block(), at=(100.0, 0.0, 0.0))
    [res] = asm.check_interference()
    assert res.status == "unknown"
    assert res.depth is None and res.volume is None
    assert "Text" in res.reason
    assert asm.check_interference(include_unknown=False) == []
    asm.check_interference(strict=True)  # unknowns never raise


def test_explicit_extents_override_estimation():
    label = text_part()
    asm = Assembly()
    asm.add_component(label)
    asm.add_component(block(), at=(100.0, 0.0, 0.0))
    set_part_extents(label, ([-10, -5, 0], [10, 5, 2]))
    assert asm.check_interference() == []
    label.set_extents(OBB.from_bounds([-10, -5, 0], [96, 5, 2]))
    [hit] = asm.check_interference()
    assert hit.status == "overlap" and hit.depth == pytest.approx(1.0)
    set_part_extents(label, None)
    assert asm.check_interference()[0].status == "unknown"
    # per-call override by path
    res = asm.check_interference(extents={"part_0": ([0, 0, 0], [1, 1, 1])})
    assert res == []


def test_estimates_for_common_operations():
    part = Part()
    sk = Sketch(part.xy())
    part.add_operation(
        Extrusion(
            Circle(sk.origin, 5.0), 10.0, end_condition=ExtrudeEndCondition.SYMMETRIC
        )
    )
    [box] = estimate_part_extents(part).boxes
    np.testing.assert_allclose(box.half, [5, 5, 5])
    np.testing.assert_allclose(box.center, [0, 0, 0], atol=1e-9)

    ball = Part()
    ball.add_operation(Sphere(Sketch(ball.xy()).origin, 3.0))
    [box] = estimate_part_extents(ball).boxes
    np.testing.assert_allclose(box.half, [3, 3, 3])

    # Lathe: a 2 × 10 profile 4..6 mm off the Y axis, revolved -> radius 6, height 10
    turned = Part()
    sk = Sketch(turned.xy())
    profile = RectangleFromCenterAndSides(Point(sk, 5.0, 5.0), 2.0, 10.0, sk)
    axis = Axis(Line(Point(sk, 0.0, 0.0), Point(sk, 0.0, 1.0)))
    turned.add_operation(Lathe(profile, axis))
    [box] = estimate_part_extents(turned).boxes
    assert sorted(np.round(box.half, 6)) == [5.0, 6.0, 6.0]

    # Extrusion on a side plane: XZ sketch extrudes along the plane normal.
    side = Part()
    sk = Sketch(side.xz())
    side.add_operation(Extrusion(Square.from_center_and_side(sk.origin, 4.0), 7.0))
    [box] = estimate_part_extents(side).boxes
    lo = box.corners().min(axis=0)
    hi = box.corners().max(axis=0)
    assert np.isclose(hi - lo, [4, 7, 4]).all() or np.isclose(hi - lo, [4, 4, 7]).all()
    assert sorted(np.round(hi - lo, 6)) == [4.0, 4.0, 7.0]

    # A part with only cuts / nothing solid is unknown.
    empty = Part()
    assert not estimate_part_extents(empty).known


def tenoned_rail(length=100.0, size=20.0, tenon=15.0, tenon_w=8.0, tenon_h=8.0):
    """Rail along +X (z in [0, size]) ending in a centred tenon, formed by
    exact rectangular shoulder cuts."""
    rail = bar(length, size, size)
    x_mid = length / 2.0 - tenon / 2.0
    cheek_w = (size - tenon_w) / 2.0
    cheek_h = (size - tenon_h) / 2.0
    sk = Sketch(rail.xy())
    for y in (-(tenon_w + cheek_w) / 2.0, (tenon_w + cheek_w) / 2.0):
        rect = RectangleFromCenterAndSides(Point(sk, x_mid, y), tenon, cheek_w, sk)
        rail.add_operation(Extrusion(rect, size, cut=True))
    for z0 in (0.0, size - cheek_h):  # top/bottom cheeks, cut from the XY plane up
        sk = Sketch(rail.xy())
        rect = RectangleFromCenterAndSides(Point(sk, x_mid, 0.0), tenon, size, sk)
        rail.add_operation(Extrusion(rect, z0 + cheek_h, start=z0, cut=True))
    return rail


def test_exact_shoulder_cuts_carve_the_tenon():
    rail = tenoned_rail()
    ext = estimate_part_extents(rail)
    assert ext.known and len(ext.boxes) > 1
    total = sum(b.volume for b in ext.boxes)
    assert total == pytest.approx(85.0 * 20 * 20 + 15.0 * 8 * 8)


def test_crossing_tenons_in_a_corner_post():
    # Two rails tenoned into a 40 mm post from adjacent faces. Their beam boxes
    # would cross inside the post; the carved tenons only cross when they sit
    # at the same height (woodworking raises JointCollisionError for that).
    def corner(tenon_dz):
        asm = Assembly()
        asm.add_component(bar(40.0, 40.0, 300.0))
        # Tenons 30 mm long, both offset 10 mm toward the shared corner.
        asm.add_component(tenoned_rail(tenon=30.0), at=(-55.0, -10.0, 200.0))
        asm.add_component(
            tenoned_rail(tenon=30.0), at=(-10.0, -55.0, 200.0 + tenon_dz), rot_deg=90
        )
        return asm.check_interference(
            allow=[("part_0", "part_1"), ("part_0", "part_2")]
        )

    [hit] = corner(0.0)
    assert {hit.path_a, hit.path_b} == {"part_1", "part_2"}
    assert hit.volume == pytest.approx(8.0 * 8.0 * 8.0)
    assert corner(10.0) == []  # staggered heights: the tenons pass each other
