"""Mate rules and connect, joints-and-interfaces follow-ups: joint limits,
connect options, computed placement (Mate.at / rotate), clock symmetry,
list-valued parameters, threaded holes, core pivot / slide / structural
interfaces, and patterns that copy joint relations."""

import math

import pytest

from cadbuildr.foundation import (
    Assembly,
    Circle,
    Extrusion,
    Part,
    Point,
    Rectangle,
    Sketch,
    TappedHole,
    ClearanceHole,
    make_anchor,
)
from cadbuildr.foundation.compute_functions import component_frames
from cadbuildr.foundation.gen.models import (
    FloatParameter,
    GearRelation,
    RevoluteJoint,
)
from cadbuildr.foundation.interfaces import (
    IncompatibleInterfaces,
    Interface,
    Mate,
    MateError,
    PivotHole,
    PivotPin,
    PlaneFace,
    ScrewHead,
    SlideCarriage,
    SlideRail,
    StructuralEnd,
    TSlot,
    export_rules,
    mate_rule,
    same_value,
)
from cadbuildr.foundation.math_utils import (
    quaternion_rotate_vector,
    tf_relative_to_frame,
)


def _body(*interfaces, size=10.0):
    """A small block carrying ``(name, spec, pos, kwargs)`` interfaces."""
    p = Part()
    p.add_operation(
        Extrusion(
            Rectangle.from_center_and_sides(Point(Sketch(p.xy()), 0, 0), size, size),
            2,
        )
    )
    for name, spec, pos, kw in interfaces:
        p.add_interface(spec, p.add_anchor(make_anchor(name, pos, **kw)))
    return p


def _world(component, anchor, asm):
    return tf_relative_to_frame(component.anchor(anchor).frame, component_frames(asm))


def _x_dir(component, anchor, asm):
    _, q = _world(component, anchor, asm)
    return quaternion_rotate_vector(q, [1.0, 0.0, 0.0])


# --------------------------------------------------------------------------- #
# Library-style interfaces and rules used below
# --------------------------------------------------------------------------- #


class GearAxis(Interface):
    """Test gear: axis anchor (+Z along the axle), module and tooth count."""

    PARAMS = ("module", "teeth")
    AXISYMMETRIC = True


@mate_rule(GearAxis, GearAxis, joint="revolute", flip=False, equal=["module"])
def gear_mesh(a, b, ctx):
    """Two spur gears in mesh: centre distance m (z1 + z2) / 2 along a's +X,
    b phased half a tooth when its tooth count is even."""
    cd = float(a.module) * (float(a.teeth) + float(b.teeth)) / 2.0
    phase = math.pi / float(b.teeth) if int(b.teeth) % 2 == 0 else 0.0
    return Mate(at=(cd, 0.0, 0.0), rotate=phase)


class SheetTab(Interface):
    PARAMS = ("t",)


class SheetSlot(Interface):
    PARAMS = ("t",)


SEEN = {}


@mate_rule(SheetTab, SheetSlot)
def tab_in_slot(tab, slot, ctx, clearance=0.1):
    """A sheet tab in a slot (records the clearance it was given)."""
    SEEN["clearance"] = clearance
    SEEN["ctx"] = dict(ctx.options)
    return None


class Hinge(Interface):
    PARAMS = ("d",)
    AXISYMMETRIC = True


@mate_rule(Hinge, Hinge, joint="revolute", limits=(0.0, math.pi / 2))
def hinge(a, b, ctx):
    """A hinge that opens 0..90 degrees."""
    return None


# --------------------------------------------------------------------------- #
# Joint limits
# --------------------------------------------------------------------------- #


def test_rule_limits_and_connect_limits_land_on_the_joint():
    base = _body(("h", Hinge(d=4), (0, 0, 2), {}))
    lid = _body(("h", Hinge(d=4), (0, 0, 0), {}))
    asm = Assembly()
    asm.ground(base)
    joint = asm.connect(base.interface("h"), lid.interface("h")).joint
    assert joint.limits.min.value == 0.0
    assert joint.limits.max.value == pytest.approx(math.pi / 2)
    with pytest.raises(ValueError, match="above limit"):
        joint.set_angle(2.0)

    lid2 = _body(("h", Hinge(d=4), (0, 0, 0), {}))
    base2 = _body(("h", Hinge(d=4), (0, 0, 2), {}))
    asm2 = Assembly()
    asm2.ground(base2)
    j2 = asm2.connect(lid2.interface("h"), base2, limits=(-1.0, None)).joint
    assert j2.limits.min.value == -1.0 and j2.limits.max is None


def test_cylindrical_limits_by_dof_and_errors():
    from cadbuildr.foundation.interfaces import Bore, Shaft

    shaft = _body(("axis", Shaft(d=8), (0, 0, 0), {}))
    hub = _body(("bore", Bore(d=8), (0, 0, 0), {}))
    asm = Assembly()
    asm.ground(shaft)
    j = asm.connect(
        shaft, hub, offset=5.0, limits={"offset": (0, 20), "angle": (None, 1)}
    ).joint
    assert j.offset_limits.max.value == 20 and j.angle_limits.max.value == 1
    with pytest.raises(MateError, match="one limited DOF"):
        asm2 = Assembly()
        s2 = _body(("axis", Shaft(d=8), (0, 0, 0), {}))
        asm2.ground(s2)
        asm2.connect(s2, _body(("bore", Bore(d=8), (0, 0, 0), {})), limits=(0, 1))
    asm3 = Assembly()
    s3 = _body(("axis", Shaft(d=8), (0, 0, 0), {}))
    asm3.ground(s3)
    with pytest.raises(MateError, match="outside its limits"):
        asm3.connect(
            s3,
            _body(("bore", Bore(d=8), (0, 0, 0), {})),
            offset=-1,
            limits={"offset": (0, 5)},
        )


def test_rigid_joint_rejects_limits():
    a = _body(("f", PlaneFace(), (0, 0, 2), {}))
    b = _body(("f", PlaneFace(), (0, 0, 0), {}))
    asm = Assembly()
    asm.ground(a)
    with pytest.raises(MateError, match="limits"):
        asm.connect(a, b, limits=(0, 1))


# --------------------------------------------------------------------------- #
# connect(**options)
# --------------------------------------------------------------------------- #


def test_connect_options_reach_the_rule_function():
    plate = _body(("slot", SheetSlot(t=1.5), (0, 0, 2), {}))
    tab = _body(("tab", SheetTab(t=1.5), (0, 0, 0), {}))
    asm = Assembly()
    asm.ground(plate)
    asm.connect(tab, plate, clearance=0.25)
    assert SEEN["clearance"] == 0.25 and SEEN["ctx"] == {"clearance": 0.25}
    rules = {r["name"]: r for r in export_rules()["rules"]}
    assert rules["tab_in_slot"]["options"] == ["clearance"]


def test_unknown_option_is_rejected():
    a = _body(("f", PlaneFace(), (0, 0, 2), {}))
    b = _body(("f", PlaneFace(), (0, 0, 0), {}))
    asm = Assembly()
    asm.ground(a)
    with pytest.raises(IncompatibleInterfaces, match="no option 'thickness'"):
        asm.connect(a.interface("f"), b.interface("f"), thickness=2)


# --------------------------------------------------------------------------- #
# Computed placement
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("parent_first", [True, False])
def test_gear_rule_computes_centre_distance_and_phase(parent_first):
    g1 = _body(("axis", GearAxis(module=2, teeth=20), (0, 0, 0), {}))
    g2 = _body(("axis", GearAxis(module=2, teeth=10), (0, 0, 0), {}))
    asm = Assembly()
    asm.ground(g1)
    pair = (g1.interface("axis"), g2.interface("axis"))
    conn = asm.connect(*(pair if parent_first else pair[::-1]))
    assert type(conn.joint).__name__ == "RevoluteJoint"
    t, _ = _world(g2, "axis", asm)
    assert t == pytest.approx([30.0, 0.0, 0.0], abs=1e-9)  # 2 * (20 + 10) / 2
    x = _x_dir(g2, "axis", asm)
    phase = math.atan2(x[1], x[0])
    assert abs(phase) == pytest.approx(math.pi / 10)


# --------------------------------------------------------------------------- #
# Clock symmetry
# --------------------------------------------------------------------------- #


class HolePattern(Interface):
    """goBILDA-style square pattern face (+Z out)."""

    PARAMS = ("pitch",)
    CLOCK_SYMMETRY = 4


mate_rule(HolePattern, HolePattern, equal=["pitch"])(None)


def test_clock_symmetry_declared_per_class_and_instance():
    assert HolePattern(pitch=16).clock_symmetry == 4
    face = PlaneFace(clock_symmetry=6)
    assert face.clock_symmetry == 6 and face.params == {"clock_symmetry": 6}
    assert PlaneFace().clock_symmetry == 1
    with pytest.raises(ValueError, match="positive integer"):
        PlaneFace(clock_symmetry=0)
    assert export_rules()["types"]["HolePattern"]["clockSymmetry"] == 4


def test_connect_clock_turns_by_symmetry_steps():
    a = _body(("p", HolePattern(pitch=16), (0, 0, 2), {}))
    b = _body(("p", HolePattern(pitch=16), (0, 0, 0), {}))
    asm = Assembly()
    asm.ground(a)
    asm.connect(a, b, clock=1)
    t, _ = _world(b, "p", asm)
    assert t == pytest.approx([0, 0, 2], abs=1e-9)
    x = _x_dir(b, "p", asm)
    assert math.degrees(math.atan2(x[1], x[0])) == pytest.approx(90.0)
    plain_a = _body(("f", PlaneFace(), (0, 0, 2), {}))
    asm2 = Assembly()
    asm2.ground(plain_a)
    with pytest.raises(MateError, match="no clock"):
        asm2.connect(plain_a, _body(("f", PlaneFace(), (0, 0, 0), {})), clock=1)


def test_loop_on_clock_symmetric_pair_snaps_to_a_step():
    """A bracket already placed 90 deg off closes its loop on a 4-fold face."""
    base = _body(
        ("top", PlaneFace(), (0, 0, 2), {}),
        ("pat", HolePattern(pitch=16), (30, 0, 2), {}),
        size=80,
    )
    bracket = _body(
        ("under", TSlot(), (0, 0, 0), {"z_down": True}),
        ("pat", HolePattern(pitch=16), (0, 0, 0), {"z_down": True}),
    )
    asm = Assembly()
    asm.ground(base)
    asm.connect(
        base.interface("top"), bracket.interface("under"), dx=30, angle=math.pi / 2
    )
    conn = asm.connect(base.interface("pat"), bracket.interface("pat"))
    assert conn.joint.parent_anchor.name.value.startswith("pat_mate")
    assert [i for i in asm.check() if i["severity"] == "error"] == []


# --------------------------------------------------------------------------- #
# List-valued parameters
# --------------------------------------------------------------------------- #


def test_list_parameters_compare_elementwise_and_by_membership():
    assert same_value([16, 32], [16.0, 32.0])
    assert not same_value([16, 32], [16, 24])
    assert not same_value([16], [16, 16])
    assert same_value("M4", ["M3", "M4"]) and not same_value(["M3"], "M4")
    pattern = HolePattern(pitch=[16, 24])
    assert pattern.pitch == [16, 24] and pattern.to_json() == '{"pitch": [16, 24]}'


# --------------------------------------------------------------------------- #
# Threaded holes
# --------------------------------------------------------------------------- #


def _block():
    p = Part()
    p.add_operation(
        Extrusion(
            Rectangle.from_center_and_sides(Point(Sketch(p.xy()), 0, 0), 40, 40), 10
        )
    )
    return p


def test_tapped_hole_fastener_binds_a_threaded_screw_hole():
    p = _block()
    a = p.add_anchor(make_anchor("tap", (0, 0, 10)))
    TappedHole(anchor=a, thread_size=5, depth=8, fastener=True)
    spec = p.interface("tap").spec
    assert spec.type_name == "ScrewHole"
    assert spec.params == {"size": "M5", "depth": 8, "thread": True}
    b = p.add_anchor(make_anchor("clear", (10, 0, 10)))
    ClearanceHole(anchor=b, size=4, depth=10, fastener=True, group="g")
    assert p.interface("clear").spec.params == {"size": "M4", "depth": 10}
    assert [n.iname for n in p.group("g")] == ["clear"]


def test_short_screw_goes_into_a_tapped_hole():
    p = _block()
    a = p.add_anchor(make_anchor("tap", (0, 0, 10)))
    TappedHole(anchor=a, thread_size=5, depth=12, fastener="M5")
    screw = _body(("head", ScrewHead(size="M5", length=8), (0, 0, 0), {}))
    asm = Assembly()
    asm.ground(p)
    assert type(asm.connect(screw, p).joint).__name__ == "RigidJoint"


# --------------------------------------------------------------------------- #
# Pivot / Slide / StructuralEnd
# --------------------------------------------------------------------------- #


def test_core_pivot_slide_and_structural_rules():
    frame = _body(
        ("pin", PivotPin(d=6), (0, 0, 2), {}),
        ("rail", SlideRail(profile="MGN12"), (0, 0, 2), {"z_axis": (1, 0, 0)}),
        ("end", StructuralEnd(section="HEA100", fixity="fixed"), (0, 0, 0), {}),
        size=60,
    )
    asm = Assembly()
    asm.ground(frame)
    link = _body(("hole", PivotHole(d=6), (0, 0, 0), {}))
    assert (
        type(asm.connect(frame.interface("pin"), link).joint).__name__
        == "RevoluteJoint"
    )
    cart = _body(
        ("run", SlideCarriage(profile="MGN12"), (0, 0, 0), {"z_axis": (1, 0, 0)})
    )
    j = asm.connect(frame.interface("rail"), cart, offset=15, limits=(0, 100)).joint
    assert type(j).__name__ == "SliderJoint" and j.limits.max.value == 100
    beam = _body(
        ("end", StructuralEnd(section="HEA100", fixity="pinned"), (0, 0, 0), {})
    )
    asm.connect(frame.interface("end"), beam.interface("end"))
    bad = _body(("end", StructuralEnd(fixity="glued"), (0, 0, 0), {}))
    with pytest.raises(IncompatibleInterfaces, match="fixity"):
        asm.connect(frame.interface("end"), bad.interface("end"))


# --------------------------------------------------------------------------- #
# Patterns copy joint relations
# --------------------------------------------------------------------------- #


def _disc(name):
    p = Part()
    p.add_operation(Extrusion(Circle(Sketch(p.xy()).origin, 5.0), 2.0))
    p.add_anchor(make_anchor(name, (0.0, 0.0, 0.0)))
    return p


def test_polar_pattern_copies_the_relation_driving_a_planet():
    asm = Assembly()
    carrier = _disc("hub")
    carrier.add_anchor(make_anchor("planet", (20.0, 0.0, 0.0)))
    asm.add_component(carrier)
    sun, planet = _disc("axis"), _disc("axis")
    sun_j = RevoluteJoint(
        parent_anchor=carrier.anchor("hub"), child_anchor=sun.anchor("axis")
    )
    planet_j = RevoluteJoint(
        parent_anchor=carrier.anchor("planet"), child_anchor=planet.anchor("axis")
    )
    asm.add_joint(sun_j)
    asm.add_joint(planet_j)
    asm.add_relation(
        GearRelation(driver=sun_j, driven=planet_j, ratio=FloatParameter(value=0.5))
    )
    planets = asm.polar_pattern(planet, 3, about=carrier.anchor("hub"))
    assert len(planets) == 3 and len(asm.relations) == 3
    sun_j.set_angle(1.0)
    driven = [j for j in asm.joints if type(j).__name__ == "RevoluteJoint"][1:]
    assert [j.angle.value for j in driven] == pytest.approx([0.5, 0.5, 0.5])


def test_replicate_copies_driving_relations():
    asm = Assembly()
    base = _disc("hub")
    for i in range(3):
        base.add_anchor(make_anchor(f"p{i}", (20.0 * (i + 1), 0.0, 0.0)))
    asm.add_component(base)
    driver, follower = _disc("axis"), _disc("axis")
    dj = RevoluteJoint(
        parent_anchor=base.anchor("hub"), child_anchor=driver.anchor("axis")
    )
    fj = RevoluteJoint(
        parent_anchor=base.anchor("p0"), child_anchor=follower.anchor("axis")
    )
    asm.add_joint(dj)
    asm.add_joint(fj)
    asm.add_relation(
        GearRelation(driver=dj, driven=fj, ratio=FloatParameter(value=2.0))
    )
    asm.replicate(follower, onto=[base.anchor("p1"), base.anchor("p2")])
    dj.set_angle(0.25)
    assert [j.angle.value for j in asm.joints[1:]] == pytest.approx([0.5] * 3)
