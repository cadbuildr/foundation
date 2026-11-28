"""Part-level / library checks (``__checks__``, reports), recursive
``assembly.check()``, frame aliases after nesting / show_dag, and the
thread-engagement check of ``screw_in_hole``."""

import pytest

from cadbuildr.foundation import (
    Assembly,
    Circle,
    Extrusion,
    Part,
    Point,
    Rectangle,
    Report,
    Sketch,
    add_check,
    collect_checks,
    issue,
    make_anchor,
)
from cadbuildr.foundation.dag_utils import show_dag
from cadbuildr.foundation.interference import check_interference
from cadbuildr.foundation.interfaces import ScrewHead, ScrewHole
from cadbuildr.foundation.interfaces.rules import thread_engagement
from cadbuildr.foundation.math_utils import frame_aliases, tf_relative_to_frame


class Box(Part):
    def __init__(self, wall=2.0):
        self.wall = wall
        sk = Sketch(self.xy())
        self.add_operation(
            Extrusion(Rectangle.from_center_and_sides(Point(sk, 0, 0), 10, 10), 10)
        )

    def __checks__(self):
        if self.wall < 0.8:
            return [
                issue(
                    "warning",
                    "printability.wall",
                    f"wall {self.wall} mm < 0.8 mm",
                    fix="thicken the wall",
                )
            ]
        return []


class Bracket(Part):
    """A hook returning bare strings / partial dicts gets them normalised."""

    def __init__(self):
        sk = Sketch(self.xy())
        self.add_operation(Extrusion(Circle(Point(sk, 0, 0), 3), 3))

    def __checks__(self):
        return ["bend radius below 1 t", {"severity": "error", "code": "dfm.k"}]


# --------------------------------------------------------------------------- #
# Frames after nesting / show_dag
# --------------------------------------------------------------------------- #


def test_sub_assembly_frame_still_chains_after_nesting():
    sub = Assembly()
    sub.add_component(Box(), at=(5, 0, 0))
    top = Assembly()
    top.add_component(sub, at=(100, 0, 0))
    t, _ = tf_relative_to_frame(sub.components[0].frame, sub.frame)
    assert t == pytest.approx([5, 0, 0])
    assert check_interference(sub) == []
    # the world transform goes through the placed root frame
    t, _ = tf_relative_to_frame(sub.components[0].frame, top.frame)
    assert t == pytest.approx([105, 0, 0])
    assert len(frame_aliases(sub.frame)) == 2


def test_frame_still_chains_after_show_dag():
    asm = Assembly()
    asm.add_component(Box(), at=(1, 2, 3))
    show_dag(asm)
    show_dag(asm)
    t, _ = tf_relative_to_frame(asm.components[0].frame, asm.frame)
    assert t == pytest.approx([1, 2, 3])
    assert asm.check() is not None


# --------------------------------------------------------------------------- #
# __checks__ / reports
# --------------------------------------------------------------------------- #


def test_part_hook_check_and_single_part_dag():
    thin = Box(wall=0.5)
    found = thin.check()
    assert [i["code"] for i in found] == ["printability.wall"]
    assert found[0]["components"] and found[0]["fix"] == "thicken the wall"
    assert set(found[0]) >= {"severity", "interfaces", "delta", "message"}
    assert [i["code"] for i in show_dag(thin)["checks"]] == ["printability.wall"]
    assert "checks" not in show_dag(Box())  # nothing to report, no key


def test_hook_results_are_normalised():
    found = Bracket().check()
    assert [(i["severity"], i["code"]) for i in found] == [
        ("warning", "check"),
        ("error", "dfm.k"),
    ]


def test_check_recurses_into_sub_assemblies_with_paths():
    inner = Assembly()
    inner.add_component(Box(wall=0.5))
    outer = Assembly()
    outer.add_component(inner)
    outer.add_component(Box(wall=0.4))
    codes = [(i["code"], i["components"]) for i in collect_checks(outer)]
    assert len(codes) == 2 and all(c == "printability.wall" for c, _ in codes)
    assert any("/" in comps[0] for _, comps in codes)  # sub/part path
    dag = show_dag(outer)
    assert len(dag["checks"]) == 2
    # assembly.check() keeps its interface issues and adds the tree's
    assert {i["code"] for i in outer.check()} >= {"printability.wall"}
    assert all(i["code"] == "coordinates" for i in outer.check(recursive=False))


def test_report_attach_reaches_check_and_dag():
    part = Box()
    report = Report("fits", data={"fit": "H7/g6"})
    report.add("info", "fit", "shaft 8 g6 in bore 8 H7: clearance 0.005..0.029")
    assert report.ok
    report.attach(part)
    add_check(part, "screening: margin 1.2")
    asm = Assembly()
    asm.add_component(part)
    codes = [i["code"] for i in collect_checks(asm)]
    assert codes == ["fit", "check"]
    assert report.to_json()["data"] == {"fit": "H7/g6"}
    assert [i["code"] for i in show_dag(asm)["checks"]] == ["fit", "check"]


# --------------------------------------------------------------------------- #
# Thread engagement
# --------------------------------------------------------------------------- #


class Screw(Part):
    def __init__(self, length):
        self.add_operation(Extrusion(Circle(Point(Sketch(self.xy()), 0, 0), 2.5), 1))
        head = self.add_anchor(make_anchor("head_seat", (0, 0, length), z_down=True))
        self.add_interface(ScrewHead(size="M5", length=length), head)


class Tapped(Part):
    def __init__(self, depth):
        self.add_operation(
            Extrusion(
                Rectangle.from_center_and_sides(Point(Sketch(self.xy()), 0, 0), 20, 20),
                10,
            )
        )
        a = self.add_anchor(make_anchor("tap", (0, 0, 10)))
        self.add_interface(ScrewHole(size="M5", depth=depth, thread=True), a)


def _tapped(length, depth):
    asm = Assembly()
    block = Tapped(depth)
    asm.ground(block)
    asm.connect(Screw(length), block.interface("tap"))
    return [i for i in asm.check() if i["severity"] != "info"]


def test_thread_engagement_helper():
    e = thread_engagement(8, "M5", 10)
    assert e["engagement"] == 8 and e["ok"] and not e["bottoms_out"]
    e = thread_engagement(12, "M5", 10, grip=6)
    assert e["engagement"] == 6 and e["ok"]
    assert not thread_engagement(4, "M5", 10)["ok"]


def test_screw_in_tapped_hole_engagement_issues():
    assert _tapped(8, 10) == []
    short = _tapped(3, 10)
    assert [i["code"] for i in short] == ["thread_engagement"]
    assert short[0]["delta"] == {"engagement": 3.0, "required": 5.0}
    assert _tapped(14, 10) == []  # bottoming out is info: shown, not blocking
    asm = Assembly()
    block = Tapped(10)
    asm.ground(block)
    asm.connect(Screw(14), block.interface("tap"))
    assert "thread_bottoms_out" in [i["code"] for i in asm.check()]
