"""FC-5/8/11/12: face planes, hole wizard tables, sketch ops, Part shortcuts."""

import math

import pytest

from cadbuildr.foundation import (
    Circle,
    ClearanceHole,
    EdgeFinder,
    Extrusion,
    ExtrudeEndCondition,
    Fillet,
    HoleFit,
    Line,
    ParallelToAxisRule,
    Part,
    Point,
    PolarPattern,
    Rectangle,
    Shell,
    Sketch,
    TappedHole,
    clearance_diameter,
    linear_copies,
    mirror,
    polar_copies,
    tap_drill_diameter,
)
from cadbuildr.foundation import (
    Emboss,
    EmbossMode,
    FaceFinder,
    InDirectionFinderRule,
    InPlaneFinderRule,
    Point3D,
    Project,
    Rip,
    SheetMetalBaseFlange,
    SheetMetalEdgeFlange,
    SheetMetalFold,
    SheetMetalToSolid,
    Text,
    TextOnPath,
    TextPathAlign,
    Unfold,
    Wrap,
)
from cadbuildr.foundation.dag_utils import show_dag


def test_hole_tables():
    assert tap_drill_diameter(6) == 5.0
    assert tap_drill_diameter(3) == 2.5
    assert clearance_diameter(6, "CLOSE") == 6.4
    assert clearance_diameter(6) == 6.6
    assert clearance_diameter(6, HoleFit.LOOSE) == 7.0
    with pytest.raises(ValueError, match="not in the ISO metric coarse table"):
        tap_drill_diameter(7)


def test_tapped_and_clearance_hole_radius():
    s = Sketch(Part().xy())
    assert TappedHole(Point(s, 0, 0), 6, 10).radius.value == pytest.approx(2.5)
    assert ClearanceHole(
        Point(s, 0, 0), 8, 10, fit=HoleFit.CLOSE
    ).radius.value == pytest.approx(4.2)


def test_end_face_plane_follows_end_condition():
    p = Part()
    s = Sketch(p.xy())
    sq = Rectangle.from_center_and_sides(s.origin, 10, 10)
    assert Extrusion(sq, 12).end_face_plane().frame.position[2] == pytest.approx(12)
    sym = Extrusion(sq, 12, end_condition=ExtrudeEndCondition.SYMMETRIC)
    assert sym.end_face_plane().frame.position[2] == pytest.approx(6)
    assert sym.start_face_plane().frame.position[2] == pytest.approx(-6)


def test_sketch_ops():
    s = Sketch(Part().xy())
    c = Circle(Point(s, 10, 0), 1)
    ring = polar_copies(c, s.origin, 4)
    assert len(ring) == 4
    assert ring[1].center.x.value == pytest.approx(0, abs=1e-9)
    assert ring[1].center.y.value == pytest.approx(10)
    row = linear_copies(c, 5, 0, 3)
    assert [r.center.x.value for r in row] == pytest.approx([10, 15, 20])
    m = mirror(c, Line(Point(s, 0, -1), Point(s, 0, 1)))
    assert m.center.x.value == pytest.approx(-10)
    # Polygon-like shapes without rotate() are copied as Polygons.
    rect = Rectangle.from_center_and_sides(Point(s, 10, 0), 2, 4)
    assert type(polar_copies(rect, s.origin, 2)[1]).__name__ == "Polygon"


def _dag_types(part):
    dag = show_dag(part)
    names = {v: k for k, v in dag["serializableNodes"].items()}
    return sorted(names[n["type"]] for n in dag["DAG"].values())


def test_shortcuts_build_the_same_dag_as_explicit_nodes():
    class Explicit(Part):
        def __init__(self):
            s = Sketch(self.xy())
            block = Extrusion(Rectangle.from_center_and_sides(s.origin, 60, 40), 25)
            self.add_operation(block)
            rounded = Fillet(
                block, 5, edge_finder=EdgeFinder(rule=ParallelToAxisRule(axis="Z"))
            )
            self.add_operation(rounded)
            self.add_operation(Shell(rounded, 2))
            self.add_operation(
                PolarPattern(Extrusion(Circle(Point(s, 12, 0), 3), 2, cut=True), 4)
            )

    class Short(Part):
        def __init__(self):
            s = Sketch(self.xy())
            block = self.extrude(Rectangle.from_center_and_sides(s.origin, 60, 40), 25)
            rounded = self.fillet(
                block, 5, EdgeFinder(rule=ParallelToAxisRule(axis="Z"))
            )
            self.shell(rounded, 2)
            self.polar_pattern(Extrusion(Circle(Point(s, 12, 0), 3), 2, cut=True), 4)

    assert _dag_types(Short()) == _dag_types(Explicit())


def test_revolve_shortcut_sets_angle_only_when_partial():
    p = Part()
    s = Sketch(p.xz())
    axis = Line(Point(s, 0, 0), Point(s, 0, 1))
    full = p.revolve(Circle(Point(s, 10, 0), 2), axis)
    part = p.revolve(Circle(Point(s, 10, 0), 2), axis, angle=90)
    assert full.angle is None
    assert part.angle.value == pytest.approx(90)
    assert math.isclose(part.axis.line.p2.y.value, 1)


def test_sheet_gauge_and_material_recorded_in_dag():
    from cadbuildr.foundation import (
        SheetMetalBaseFlange,
        SheetMetalToSolid,
        sheet_thickness,
    )

    assert sheet_thickness("aluminum_5052", 16) == pytest.approx(1.291)
    with pytest.raises(ValueError, match="Unknown material"):
        sheet_thickness("unobtanium", 16)

    class Panel(Part):
        def __init__(self):
            s = Sketch(self.xy())
            base = SheetMetalBaseFlange(
                profile=Rectangle.from_center_and_sides(s.origin, 40, 20),
                thickness=sheet_thickness("cold_rolled_steel", 16),
                material="cold_rolled_steel",
            )
            self.add_operation(SheetMetalToSolid(body=base))

    dag = show_dag(Panel())
    strings = [
        n["params"].get("value")
        for n in dag["DAG"].values()
        if n["type"] == dag["serializableNodes"]["StringParameter"]
    ]
    assert "cold_rolled_steel" in strings


def test_trim_extend_intersect():
    from cadbuildr.foundation import extend, intersect, trim_corner

    s = Sketch(Part().xy())
    a = Line(Point(s, 0, 0), Point(s, 5, 0))
    b = Line(Point(s, 10, 2), Point(s, 10, 8))
    c = intersect(a, b)
    assert (c.x.value, c.y.value) == pytest.approx((10, 0))
    ta, tb = trim_corner(a, b)
    assert ta.p2.x.value == pytest.approx(10) and tb.p1.y.value == pytest.approx(0)
    longer = extend(a, start=1, end=2)
    assert longer.p1.x.value == pytest.approx(
        -1
    ) and longer.p2.x.value == pytest.approx(7)
    with pytest.raises(ValueError, match="parallel"):
        intersect(a, Line(Point(s, 0, 1), Point(s, 5, 1)))


def test_rib_expands_to_symmetric_extrusion():
    from cadbuildr.foundation import Rib

    s = Sketch(Part().xz())
    ext = Rib([Point(s, 0, 0), Point(s, 20, 0), Point(s, 0, 15)], 3).expand()
    assert (ext.start.value, ext.end.value) == pytest.approx((-1.5, 1.5))
    assert len(ext.shape[0].lines) == 3
    with pytest.raises(ValueError, match="at least 3 points"):
        Rib([Point(s, 0, 0), Point(s, 1, 0)], 3).expand()  # computes are lazy


# --- Remaining gaps: Project, Emboss, Wrap, Rip, TextOnPath, partial Fold -------------


def _dag_nodes(obj, type_name):
    dag = show_dag(obj)
    type_id = dag["serializableNodes"][type_name]
    return [n for n in dag["DAG"].values() if n["type"] == type_id]


def test_new_solid_ops_serialize_with_named_defaults():
    p = Part()
    s = Sketch(p.xy())
    block = Extrusion(Rectangle.from_center_and_sides(s.origin, 30, 20), 10)
    top = FaceFinder(rule=InPlaneFinderRule(p.xy(), 10))
    above = Sketch(p.xy().get_parallel_plane(15))
    emboss = Emboss(block, Circle(above.origin, 3), top, 1.0)
    assert emboss.mode == EmbossMode.RAISE
    assert emboss.sketch is above
    rip = Rip(block, EdgeFinder(rule=InDirectionFinderRule(Point3D(0, 0, 1))))
    assert rip.gap.value == 0.5
    p.add_operation(Wrap(emboss, Circle(above.origin, 2), top, 0.5, mode=EmbossMode.ENGRAVE))
    p.add_operation(Project(block, "XY"))
    for name in ["Emboss", "Wrap", "Project"]:
        assert len(_dag_nodes(p, name)) == 1


def test_text_on_path_defaults_and_optional_font():
    p = Part()
    s = Sketch(p.xy())
    t = TextOnPath(Circle(s.origin, 20), "HELLO", 5)
    assert t.align == TextPathAlign.START
    assert t.start.value == 0.0 and t.baseline_offset.value == 0.0
    assert t.font_url is None and t.sketch is s
    assert Text(s, "Hi", 5).font_url is None  # kernel default font


def test_fold_refold_points_at_the_same_flange_node_as_the_unfolded_chain():
    """Regression: an object reached along two paths must serialize to ONE node,
    even if compute fields grow a shared Sketch between the two visits."""
    p = Part()
    s = Sketch(p.xy())
    base = SheetMetalBaseFlange(profile=Rectangle.from_center_and_sides(s.origin, 80, 40), thickness=2)
    front = SheetMetalEdgeFlange(body=base, edge=Line(Point(s, -40, -20), Point(s, 40, -20)), length=25)
    back = SheetMetalEdgeFlange(body=front, edge=Line(Point(s, 40, 20), Point(s, -40, 20)), length=25)
    p.add_operation(SheetMetalToSolid(body=SheetMetalFold(body=Unfold(body=back), refold=[front])))
    assert len(_dag_nodes(p, "SheetMetalEdgeFlange")) == 2
    assert len(_dag_nodes(p, "SheetMetalBaseFlange")) == 1
