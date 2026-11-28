"""Public component API and the bugs reported by the library waves (Nov 27):
owner_of / source_of / component_extents, identical placed instances in
check_interference, settable ``head``, names set after placement, ground poses,
scale_about and plane_from_normal."""

import json
import math

import numpy as np
import pytest

from cadbuildr.foundation import (
    Assembly,
    BoolParameter,
    Extrusion,
    FloatParameter,
    MoveBody,
    Part,
    RigidJoint,
    Scale,
    Sketch,
    Sphere,
    Square,
    StringParameter,
    Text,
    anchor_plane,
    component_extents,
    make_anchor,
    owner_of,
    plane_from_normal,
    scale_about,
    show_dag,
    source_of,
)
from cadbuildr.foundation.compute_functions import _anchor_owner
from cadbuildr.foundation.interfaces import PlaneFace
from cadbuildr.foundation.math_utils import tf_relative_to_frame


class Block(Part):
    """size x size x height, centred in XY, z in [0, height], on the part's xy."""

    def __init__(self, size=10.0, height=10.0):
        super().__init__()
        s = Sketch(self.xy())
        self.add_operation(
            Extrusion(Square.from_center_and_side(s.origin, size), height)
        )
        self.bottom = self.add_anchor(make_anchor("bottom", (0, 0, 0), z_down=True))


class FreePlanePost(Part):
    """Sketched on a free-standing plane (``anchor_plane(make_anchor(...))``,
    never attached): the kernel reads it in the part's own coordinates."""

    def __init__(self):
        super().__init__()
        s = Sketch(anchor_plane(make_anchor("_sketch", (0.0, 0.0, 0.0))))
        self.add_operation(Extrusion(Square.from_center_and_side(s.origin, 5.0), 6.0))


# --------------------------------------------------------------------------- #
# owner_of / source_of
# --------------------------------------------------------------------------- #


def test_owner_of_anchor_and_interface_and_private_alias():
    part = Block()
    node = part.add_interface(PlaneFace(name="bottom"), part.bottom)
    assert owner_of(part.bottom) is part
    assert owner_of(node) is part
    assert _anchor_owner(part.bottom) is part  # private name keeps working
    with pytest.raises(ValueError, match="no owner"):
        owner_of(make_anchor("loose"))
    with pytest.raises(TypeError):
        owner_of(42)


def test_source_of_placed_root_is_the_live_part():
    asm = Assembly()
    part = Block()
    asm.add_component(part, at=(5, 0, 0))
    root = asm.components[0]
    assert root is not part
    assert source_of(root) is part
    assert source_of(part) is part
    assert root.__dict__["_source_component"] is part  # private attr kept


# --------------------------------------------------------------------------- #
# component_extents
# --------------------------------------------------------------------------- #


def test_component_extents_of_part_and_assembly():
    ext = component_extents(Block(10, 4))
    assert ext.known
    assert np.allclose(ext.lo, (-5, -5, 0)) and np.allclose(ext.hi, (5, 5, 4))
    assert np.allclose(ext.size, (10, 10, 4))

    asm = Assembly()
    asm.add_component(Block(10, 4), at=(0, 0, 0))
    asm.add_component(Block(10, 4), at=(30, 0, 0), rot_deg=(90, 0, 0))
    ext = component_extents(asm)
    assert ext.known
    assert np.allclose(ext.lo, (-5, -5, -5)) and np.allclose(ext.hi, (35, 5, 5))


def test_component_extents_reports_unbounded_parts():
    part = Part()
    ext = component_extents(part)
    assert not ext.known and ext.lo is None


def test_text_extents_estimate_is_opt_in_for_interference():
    from cadbuildr.foundation import estimate_part_extents

    part = Part()
    s = Sketch(part.xy())
    part.add_operation(Extrusion(Text(s, "AB", 10.0), 2.0))
    assert not estimate_part_extents(part).known  # unchanged default
    ext = component_extents(part)
    assert ext.known
    # 2 glyphs of <= 1 em, ascender 1 em, descender 0.3 em, 0.1 em bearing.
    assert np.allclose(ext.lo, (-1.0, -3.0, 0.0))
    assert np.allclose(ext.hi, (20.0, 10.0, 2.0))


# --------------------------------------------------------------------------- #
# check_interference: identical instances (enclosures' spacers)
# --------------------------------------------------------------------------- #


def test_identical_instances_on_free_planes_do_not_overlap():
    asm = Assembly()
    for x in (0.0, 20.0, 40.0):
        asm.add_component(FreePlanePost(), at=(x, 0.0, 0.0))
    assert asm.check_interference() == []
    ext = component_extents(asm)
    assert np.allclose(ext.lo, (-2.5, -2.5, 0)) and np.allclose(ext.hi, (42.5, 2.5, 6))


def test_identical_instances_placed_by_joints_do_not_overlap():
    base = Block(100, 2)
    spots = [
        base.add_anchor(make_anchor(f"s{i}", (x, 0, 2)))
        for i, x in enumerate((-30, 0, 30))
    ]
    asm = Assembly()
    asm.ground(base)
    for spot in spots:
        post = FreePlanePost()
        foot = post.add_anchor(make_anchor("foot", (0, 0, 0), z_down=True))
        asm.add_joint(
            RigidJoint(
                parent_anchor=spot, child_anchor=foot, flip=BoolParameter(value=False)
            )
        )
    assert asm.check_interference() == []


def test_really_overlapping_free_plane_parts_still_reported():
    asm = Assembly()
    asm.add_component(FreePlanePost(), at=(0, 0, 0))
    asm.add_component(FreePlanePost(), at=(2, 0, 0))
    hits = asm.check_interference()
    assert len(hits) == 1 and hits[0].depth == pytest.approx(3.0)


def test_check_interference_after_show_dag():
    asm = Assembly()
    asm.add_component(Block(), at=(0, 0, 0))
    asm.add_component(Block(), at=(5, 0, 0))
    show_dag(asm)  # converts the tree to roots (a viewer rebuild)
    hits = asm.check_interference()
    assert len(hits) == 1 and hits[0].depth == pytest.approx(5.0)


# --------------------------------------------------------------------------- #
# Reserved attribute names
# --------------------------------------------------------------------------- #


def test_head_can_be_assigned_on_parts_and_assemblies():
    class Robot(Assembly):
        def __init__(self):
            super().__init__()
            self.head = Block()
            self.add_component(self.head)

    robot = Robot()
    assert isinstance(robot.head, Block)
    part = Part()
    assert part.head.frame is part.frame  # legacy alias when not assigned
    part.head = "screw head"
    assert part.head == "screw head"


def test_read_only_attribute_error_names_it():
    from cadbuildr.foundation.gen.models import Part as PartModel

    prop = property(lambda self: 1)
    setattr(PartModel, "demo_read_only", prop)
    try:
        with pytest.raises(AttributeError, match="'demo_read_only' is a reserved"):
            Part().demo_read_only = 3
    finally:
        delattr(PartModel, "demo_read_only")


# --------------------------------------------------------------------------- #
# Names set after placement survive re-conversion (viewer rebuild)
# --------------------------------------------------------------------------- #


def test_part_name_set_after_placement_reaches_the_dag():
    class Frame(Assembly):
        def __init__(self):
            super().__init__()
            self.leg = Block()
            self.add_component(self.leg)
            self.leg.name = StringParameter(value="left_leg")
            self.sub = Assembly()
            self.sub.add_component(Block())
            self.add_component(self.sub)
            self.sub.name = StringParameter(value="shelf")

    asm = Frame()
    for _ in range(2):  # every rebuild keeps them
        dag = json.dumps(show_dag(asm))
        assert "left_leg" in dag and "shelf" in dag


# --------------------------------------------------------------------------- #
# ground poses
# --------------------------------------------------------------------------- #


def _placed_tf(asm):
    return tf_relative_to_frame(asm.components[0].frame, asm.frame)


def test_ground_component_with_at_and_rot_deg():
    asm = Assembly()
    asm.ground(Block(), at=(1, 2, 3), rot_deg=90)
    t, q = _placed_tf(asm)
    assert np.allclose(t, (1, 2, 3))
    assert np.allclose(q, (math.cos(math.pi / 4), 0, 0, math.sin(math.pi / 4)))
    assert asm.check() is not None


def test_ground_component_with_direction_vectors():
    asm = Assembly()
    asm.ground(Block(), z_axis=(1, 0, 0), x_axis=(0, 1, 0), at=(0, 0, 5))
    ext = component_extents(asm)
    # The block's +Z (height 10) now runs along world +X.
    assert np.allclose(ext.lo, (0, -5, 0)) and np.allclose(ext.hi, (10, 5, 10))


def test_ground_anchor_with_direction_vectors_and_bad_args():
    asm = Assembly()
    part = Block()
    asm.ground(part.bottom, z_axis=(0, 0, 1))
    assert len(asm.joints) == 1
    with pytest.raises(TypeError):
        Assembly().ground(Block(), rot_deg=10, z_axis=(1, 0, 0))
    with pytest.raises(ValueError):
        Assembly().ground(Block(), x_axis=(1, 0, 0))


# --------------------------------------------------------------------------- #
# scale_about / plane_from_normal
# --------------------------------------------------------------------------- #


def test_scale_about_composes_move_scale_move():
    part = Part()
    s = Sketch(part.xy())
    sphere = Sphere(s.origin, radius=1)
    op = scale_about(sphere, 1.5, (0, 0, 10))
    assert isinstance(op, MoveBody) and isinstance(op.shape, Scale)
    assert isinstance(op.shape.shape, MoveBody)
    assert op.translation.z.value == 10 and op.shape.shape.translation.z.value == -10
    assert op.shape.factor.value == 1.5
    part.add_operation(op)
    dag = show_dag(part)
    assert "Scale" in dag["serializableNodes"]
    assert isinstance(scale_about(sphere, 2.0), Scale)  # about the origin
    with pytest.raises(ValueError):
        scale_about(sphere, 0.0)


def test_plane_from_normal_hangs_from_the_part():
    part = Block()
    plane = plane_from_normal(part, (0, 0, 5), (1, 0, 0))
    assert plane.frame.top_frame is part.frame
    t, q = tf_relative_to_frame(plane.frame, part.frame)
    assert np.allclose(t, (0, 0, 5))
    z = plane.get_z_axis() if hasattr(plane, "get_z_axis") else None
    if z is not None:
        assert np.allclose(z, (1, 0, 0))
    s = Sketch(plane)
    part.add_operation(Extrusion(Square.from_center_and_side(s.origin, 2.0), 3.0))
    ext = component_extents(part)
    assert ext.hi[0] == pytest.approx(5.0)  # the block still bounds +X
    assert plane_from_normal(None, (1, 0, 0), (0, 1, 0)).frame.top_frame is None
