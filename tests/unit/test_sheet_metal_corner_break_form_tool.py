"""SheetMetalCornerBreak and SheetMetalFormTool serialize as native DAG nodes."""

from cadbuildr.foundation import (
    CornerBreakType,
    Extrusion,
    Part,
    Point,
    Rectangle,
    SheetMetalBaseFlange,
    SheetMetalCornerBreak,
    SheetMetalFormTool,
    SheetMetalToSolid,
    Sketch,
)
from cadbuildr.foundation.dag_utils import show_dag


def _nodes(part, type_name):
    dag = show_dag(part)
    names = {v: k for k, v in dag["serializableNodes"].items()}
    return [
        (nid, n) for nid, n in dag["DAG"].items() if names[n["type"]] == type_name
    ], dag


def _plate(p):
    s = Sketch(p.xy())
    base = SheetMetalBaseFlange(
        profile=Rectangle.from_center_and_sides(s.origin, 60, 40), thickness=2
    )
    return s, base


def test_corner_break_defaults_to_fillet_and_records_its_sketch():
    p = Part()
    s, base = _plate(p)
    body = SheetMetalCornerBreak(base, [Point(s, 30, 20), Point(s, -30, 20)], 5)
    assert body.break_type == CornerBreakType.FILLET
    assert body.sketch is s
    p.add_operation(SheetMetalToSolid(body=body))
    nodes, dag = _nodes(p, "SheetMetalCornerBreak")
    assert len(nodes) == 1
    deps = nodes[0][1]["deps"]
    assert len(deps["corners"]) == 2
    assert "sketch" in deps and "body" in deps


def test_corner_break_chamfer():
    p = Part()
    s, base = _plate(p)
    body = SheetMetalCornerBreak(
        base, [Point(s, 30, 20)], 3, break_type=CornerBreakType.CHAMFER
    )
    p.add_operation(SheetMetalToSolid(body=body))
    nodes, _ = _nodes(p, "SheetMetalCornerBreak")
    assert nodes[0][1]["params"]["break_type"] == "CHAMFER"


def test_form_tool_takes_a_solid_and_a_face():
    p = Part()
    _, base = _plate(p)
    top = p.xy().get_parallel_plane(2)
    tool = Extrusion(Rectangle.from_center_and_sides(Sketch(top).origin, 20, 10), 5)
    p.add_operation(SheetMetalToSolid(body=SheetMetalFormTool(base, tool, top)))
    nodes, dag = _nodes(p, "SheetMetalFormTool")
    assert len(nodes) == 1
    deps = nodes[0][1]["deps"]
    names = {v: k for k, v in dag["serializableNodes"].items()}
    assert names[dag["DAG"][deps["tool"]]["type"]] == "Extrusion"
    assert names[dag["DAG"][deps["face"]]["type"]] == "Plane"
