"""Interfaces: typed mating sites, mate rules, connect / connect_all /
expose / ground, check() and the constraint-status errors (spec section 7)."""

import io
import json
import math
from contextlib import redirect_stdout

import pytest

from cadbuildr.foundation import (
    Assembly,
    Circle,
    Extrusion,
    Hole,
    Part,
    Point,
    Rectangle,
    Sketch,
    make_anchor,
)
from cadbuildr.foundation.dag_utils import show_dag
from cadbuildr.foundation.interfaces import (
    AmbiguousConnect,
    BearingFace,
    Bore,
    IncompatibleInterfaces,
    Interface,
    LoopMismatch,
    PlaneFace,
    RodAxis,
    RodEnd,
    RodHole,
    ScrewHead,
    ScrewHole,
    Shaft,
    UnsolvedLoop,
    export_rules,
    features,
    mate_rule,
)
from cadbuildr.foundation.math_utils import tf_relative_to_frame

# --------------------------------------------------------------------------- #
# Test parts
# --------------------------------------------------------------------------- #


class Plate(Part):
    """40 x 40 x 5 plate, M5 holes at +-pitch/2 (fastener= holes), rod holes."""

    def __init__(self, pitch=20.0, size="M5", rod=8.0):
        self.add_operation(
            Extrusion(
                Rectangle.from_center_and_sides(Point(Sketch(self.xy()), 0, 0), 60, 60),
                5,
            )
        )
        for i, x in enumerate((-pitch / 2, pitch / 2)):
            a = self.add_anchor(make_anchor(f"hole_{i}", (x, 0, 5)))
            self.add_operation(
                Hole(anchor=a, radius=2.75, depth=5, fastener=size, group="mount")
            )
        for i, x in enumerate((-pitch / 2, pitch / 2)):
            a = self.add_anchor(make_anchor(f"rod_{i}", (x, 20, 5), z_down=True))
            features.RodHole(face=a, d=rod, depth=5)
        self.add_interface(PlaneFace(), self.add_anchor(make_anchor("top", (0, 0, 5))))
        self.add_interface(
            PlaneFace(), self.add_anchor(make_anchor("bottom", (0, 0, 0), z_down=True))
        )


class Screw(Part):
    def __init__(self, size="M5", length=12.0):
        d = float(size[1:])
        self.add_operation(
            Extrusion(Circle(Point(Sketch(self.xy()), 0, 0), d / 2), length)
        )
        head = self.add_anchor(make_anchor("head_seat", (0, 0, length), z_down=True))
        self.add_interface(ScrewHead(size=size, length=length), head)


class Rod(Part):
    def __init__(self, d=8.0, length=100.0):
        self.add_operation(
            Extrusion(Circle(Point(Sketch(self.xy()), 0, 0), d / 2), length)
        )
        features.ShaftFeature(self, d=d, length=length)  # Shaft + ShaftEnd
        self.add_interface(
            RodEnd(d=d),
            self.add_anchor(make_anchor("rod_end_a", (0, 0, 0), z_down=True)),
        )
        self.add_interface(
            RodEnd(d=d), self.add_anchor(make_anchor("rod_end_b", (0, 0, length)))
        )
        self.add_interface(
            RodAxis(d=d), self.add_anchor(make_anchor("rod_axis", (0, 0, 0)))
        )


class Bush(Part):
    """Linear bushing sliding on a rod (BearingFace on its end)."""

    def __init__(self, d=8.0):
        self.add_operation(Extrusion(Circle(Point(Sketch(self.xy()), 0, 0), d), 10))
        end = self.add_anchor(make_anchor("end", (0, 0, 0), z_down=True))
        self.add_interface(BearingFace(model="LM8UU", d=d), end)


def _world(component, anchor, asm):
    t, _ = tf_relative_to_frame(component.anchor(anchor).frame, asm.frame)
    return t


# --------------------------------------------------------------------------- #
# Binding interfaces
# --------------------------------------------------------------------------- #


def test_add_interface_lookup_group_and_dag():
    p = Plate()
    assert p.interface("hole_0").type.value == "ScrewHole"
    assert json.loads(p.interface("hole_0").params.value) == {"size": "M5", "depth": 5}
    assert [n.iname for n in p.group("mount")] == ["hole_0", "hole_1"]
    with pytest.raises(KeyError, match="available"):
        p.interface("nope")
    with pytest.raises(KeyError, match="groups"):
        p.group("nope")
    dag = show_dag(p)
    names = {v: k for k, v in dag["serializableNodes"].items()}
    ifaces = [n for n in dag["DAG"].values() if names[n["type"]] == "Interface"]
    assert len(ifaces) == len(p.interfaces) == 6
    root = dag["DAG"][dag["rootNodeId"]]
    assert len(root["deps"]["interfaces"]) == 6


def test_part_without_interfaces_serializes_without_the_field():
    p = Part()
    p.add_operation(Extrusion(Circle(Point(Sketch(p.xy()), 0, 0), 1), 1))
    root = show_dag(p)["DAG"][show_dag(p)["rootNodeId"]]
    assert "interfaces" not in root["params"] and "interfaces" not in root["deps"]


def test_fastener_hole_needs_an_anchor():
    p = Part()
    with pytest.raises(TypeError, match="anchor"):
        Hole(Point(Sketch(p.xy()), 0, 0), 2.0, 5.0, fastener="M4")


def test_features_create_geometry_and_interfaces():
    p = Part()
    p.add_operation(
        Extrusion(
            Rectangle.from_center_and_sides(Point(Sketch(p.xy()), 0, 0), 80, 80), 10
        )
    )
    face = p.add_anchor(make_anchor("front", (0, 0, 10)))
    n_ops = len(p.operations)
    features.BearingPocket(face=face, model="608", name="seat", depth=10, through_d=10)
    assert p.interface("seat").type.value == "BearingSeat"
    t, _ = tf_relative_to_frame(p.anchor("seat").frame, p.frame)
    assert t == pytest.approx([0, 0, 3])  # 10 - 608 width
    under = p.add_anchor(make_anchor("under", (20, 0, 0), z_down=True))
    features.NemaMount(face=under, frame="NEMA17", depth=10)
    assert len(p.group("motor")) == 4
    assert p.interface("under").type.value == "NemaFace"
    assert len(p.operations) == n_ops + 2 + 5


# --------------------------------------------------------------------------- #
# connect
# --------------------------------------------------------------------------- #


def test_connect_places_screw_on_hole_and_connect_all_fills_a_group():
    p = Plate()
    asm = Assembly()
    asm.ground(p)
    s = Screw()
    conn = asm.connect(s, p.interface("hole_0"))  # component-level: unique pair
    assert type(conn.joint).__name__ == "RigidJoint"
    assert [i.iname for i in conn.interfaces] == ["hole_0", "head_seat"]
    assert _world(s, "head_seat", asm) == pytest.approx([-10, 0, 5])
    screws = asm.connect_all(Screw, p.group("mount"))
    assert len(screws) == 2 and len(asm.components) == 4
    assert [i for i in asm.check() if i["severity"] != "info"] == []


def test_incompatible_interfaces_raise_with_reason():
    p = Plate()
    asm = Assembly()
    asm.ground(p)
    with pytest.raises(IncompatibleInterfaces, match="size") as err:
        asm.connect(Screw("M4").interface("head_seat"), p.interface("hole_0"))
    assert err.value.reason
    with pytest.raises(IncompatibleInterfaces, match="no mate rule"):
        asm.connect(Screw().interface("head_seat"), p.interface("top"))


def test_ambiguous_component_connect_lists_candidates():
    p = Plate()
    asm = Assembly()
    asm.ground(p)
    with pytest.raises(AmbiguousConnect) as err:
        asm.connect(Screw(), p)
    assert len(err.value.candidates) == 2


def test_neither_placed_is_an_error():
    asm = Assembly()
    with pytest.raises(ValueError, match="ground"):
        asm.connect(Screw(), Plate().interface("hole_0"))


def test_slider_dof_and_moves_info():
    p = Plate()
    asm = Assembly()
    asm.ground(p)
    rod = Rod()
    asm.connect(rod.interface("rod_end_a"), p.interface("rod_0"))
    bush = Bush()
    conn = asm.connect(bush.interface("end"), rod.interface("rod_axis"), offset=40)
    assert type(conn.joint).__name__ == "SliderJoint"
    moves = [i for i in asm.check() if i["code"] == "moves"]
    assert moves and moves[0]["delta"] == {"dof": {"offset": 40.0}}


def _two_plates(a, b):
    asm = Assembly()
    asm.ground(a)
    r0, r1 = Rod(), Rod()
    asm.connect(r0.interface("rod_end_a"), a.interface("rod_0"))
    asm.connect(r1.interface("rod_end_a"), a.interface("rod_1"))
    asm.connect(b.interface("rod_0"), r0.interface("rod_end_b"))  # b hangs from rod 0
    return asm, r0, r1


def test_consistent_loop_is_checked_and_symmetric_twist_is_free():
    a, b = Plate(), Plate()
    asm, r0, r1 = _two_plates(a, b)
    with pytest.raises(LoopMismatch):  # the wrong hole: 20 mm off
        asm.connect(b.interface("rod_0"), r1.interface("rod_end_b"))
    # RodEnd / RodHole are axisymmetric: the twist about the rod is free
    conn = asm.connect(b.interface("rod_1"), r1.interface("rod_end_b"))
    assert conn.joint is not None and len(asm.joints) == 3  # a loop adds no joint
    assert [i for i in asm.check() if i["severity"] == "error"] == []


def test_inconsistent_loop_reports_delta_and_the_inputs_that_disagree():
    """Deliberately inconsistent: the second plate's hole spacing differs."""
    from cadbuildr.foundation.library import Num, part

    @part(category="Test")
    class SpacedPlate(Plate):
        def __init__(self, spacing: Num(min=10, max=50) = 20.0):
            super().__init__(pitch=spacing)

    a, b = SpacedPlate(spacing=20.0), SpacedPlate(spacing=24.0)
    asm, r0, r1 = _two_plates(a, b)
    with pytest.raises(LoopMismatch) as err:
        asm.connect(b.interface("rod_1"), r1.interface("rod_end_b"))
    e = err.value
    assert e.delta_mm == pytest.approx(4.0) and e.delta_deg == pytest.approx(
        0.0, abs=1e-6
    )
    assert abs(e.along[0]) == pytest.approx(1.0)
    assert "spacing" in e.hint and "20" in e.hint and "24" in e.hint


def test_loop_through_a_moving_joint_is_unsolved():
    from cadbuildr.foundation.interfaces import NutSeat

    p = Plate()
    p.add_interface(
        ScrewHole(size="M5"),
        p.add_anchor(make_anchor("under_rod", (-10, 20, 0), z_down=True)),
    )
    asm = Assembly()
    asm.ground(p)
    rod = Rod()
    asm.connect(rod.interface("rod_end_a"), p.interface("rod_0"))
    bush = Bush()
    bush.add_interface(
        NutSeat(size="M5"), bush.add_anchor(make_anchor("face", (0, 0, 0), z_down=True))
    )
    slide = asm.connect(
        bush.interface("end"), rod.interface("rod_axis"), offset=40
    ).joint
    # the bush face against the plate underside: 35 mm off along the rod,
    # which the slider could take up -> unsolved, not inconsistent
    with pytest.raises(UnsolvedLoop) as err:
        asm.connect(bush.interface("face"), p.interface("under_rod"))
    assert err.value.joint is slide
    assert err.value.delta_mm == pytest.approx(35.0)
    slide.set_offset(5.0)  # now it closes
    asm.connect(bush.interface("face"), p.interface("under_rod"))
    # moving the slider again breaks the loop: check() reports it
    slide.set_offset(10.0)
    loops = [i for i in asm.check() if i["code"] == "loop"]
    assert loops and loops[0]["delta"]["mm"] == pytest.approx(5.0)


def test_check_reports_coordinates_unconnected_and_broken_loops():
    p = Plate()
    p.add_interface(
        Bore(d=5), p.add_anchor(make_anchor("must", (0, -20, 5))), required=True
    )
    asm = Assembly()
    asm.ground(p)
    asm.add_component(Screw(), at=(100, 0, 0))
    rod = Rod()
    asm.connect(rod.interface("rod_end_a"), p.interface("rod_0"))
    bush, bush2 = Bush(), Bush()
    slide = asm.connect(
        bush.interface("end"), rod.interface("rod_axis"), offset=10
    ).joint
    issues = asm.check()
    codes = {i["code"] for i in issues}
    assert {"coordinates", "unconnected", "moves"} <= codes
    for issue in issues:
        assert set(issue) == {
            "severity",
            "code",
            "interfaces",
            "components",
            "delta",
            "message",
            "fix",
        }
    # the issues travel with the DAG and the run output
    dag = show_dag(asm)
    assert {i["code"] for i in dag["checks"]} == codes
    from cadbuildr.foundation.dag_utils import report_checks

    out = io.StringIO()
    with redirect_stdout(out):
        report_checks(dag["checks"])
    assert "check: warning coordinates" in out.getvalue()
    assert slide is not None and bush2 is not None


def test_expose_lets_a_parent_connect_a_sub_assembly():
    sub = Assembly()
    rod, plate = Rod(length=50), Plate()
    sub.ground(plate)
    sub.connect(rod.interface("rod_end_a"), plate.interface("rod_0"))
    node = sub.expose(rod.interface("end_b"), as_="tip")
    assert node.type.value == "ShaftEnd" and sub.interface("tip") is node

    class Cup(Part):
        def __init__(self):
            self.add_operation(
                Extrusion(Circle(Point(Sketch(self.xy()), 0, 0), 10), 10)
            )
            self.add_interface(
                PlaneFace(),
                self.add_anchor(make_anchor("base", (0, 0, 0), z_down=True)),
            )
            self.add_interface(
                Bore(d=8), self.add_anchor(make_anchor("stop", (0, 0, 10)))
            )

    top, base, cup = Assembly(), Plate(), Cup()
    top.ground(base)
    top.connect(cup.interface("base"), base.interface("top"))
    conn = top.connect(
        sub.interface("tip"), cup.interface("stop")
    )  # places the sub-assembly
    assert conn.joint.child_anchor is sub.anchor("tip")
    t, _ = tf_relative_to_frame(sub.anchor("tip").frame, top.frame)
    assert t == pytest.approx([0, 0, 15])
    assert [i for i in top.check() if i["severity"] != "info"] == []


def test_custom_rule_and_declarative_export():
    class Peg(Interface):
        PARAMS = ("d",)

    class Socket(Interface):
        PARAMS = ("d",)

    @mate_rule(Peg, Socket, joint="revolute", equal=["d"], dof={"angle": 0.5})
    def peg_in_socket(peg, socket, ctx):
        """A peg turns in its socket."""
        ctx.require(peg.d <= 20, "peg too big")

    doc = export_rules()
    assert doc["format"] == "cadbuildr.mate-rules/1"
    rule = next(r for r in doc["rules"] if r["name"] == "peg_in_socket")
    assert rule == {
        "name": "peg_in_socket",
        "a": "Peg",
        "b": "Socket",
        "joint": "revolute",
        "jointType": "RevoluteJoint",
        "flip": True,
        "equal": [["d", "d"]],
        "dof": {"angle": 0.5},
        "dofNames": ["angle"],
        "checks": True,
        "doc": "A peg turns in its socket.",
    }
    assert doc["types"]["ScrewHole"]["params"] == ["size", "depth", "thread", "drilled"]
    assert {"rigid", "slider", "revolute", "cylindrical", "planar"} <= set(
        doc["joints"]
    )
    with pytest.raises(ValueError, match="unknown joint"):
        mate_rule(Peg, Socket, joint="glue")


def test_undrilled_hole_gets_a_clearance_modifier():
    p = Plate()
    p.add_interface(
        ScrewHole(size="M5", depth=5, drilled=False),
        p.add_anchor(make_anchor("blank", (0, -20, 5))),
    )
    asm = Assembly()
    asm.ground(p)
    n = len(p.operations)
    conn = asm.connect(Screw(), p.interface("blank"))
    assert len(conn.modifiers) == 1 and len(p.operations) == n + 1


def test_shaft_in_bore_is_cylindrical_and_coaxial():
    p = Plate()
    asm = Assembly()
    asm.ground(p)
    rod = Rod()
    asm.connect(rod.interface("rod_end_a"), p.interface("rod_0"))

    class Wheel(Part):
        def __init__(self):
            self.add_operation(Extrusion(Circle(Point(Sketch(self.xy()), 0, 0), 20), 5))
            self.add_interface(
                Bore(d=8), self.add_anchor(make_anchor("axis", (0, 0, 0)))
            )

    w = Wheel()
    conn = asm.connect(w, rod.interface("axis"), offset=30, angle=math.pi / 3)
    assert type(conn.joint).__name__ == "CylindricalJoint"
    t, _ = tf_relative_to_frame(w.anchor("axis").frame, asm.frame)
    assert t == pytest.approx([-10, 20, 5 - 30])  # the rod runs down from the hole
