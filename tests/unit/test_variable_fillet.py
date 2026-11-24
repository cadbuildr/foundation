"""Variable fillet through radius control points: ``Fillet.radius_points`` and
the ``radius_end`` / ``radius_points`` arguments of ``Part.fillet`` /
``Part.fillet_edges``."""

import pytest

from cadbuildr.foundation import (
    Fillet,
    FilletRadiusPoint,
    Part,
    Point,
    Rectangle,
    Sketch,
)
from cadbuildr.foundation.dag_utils import show_dag


def block():
    p = Part()
    s = Sketch(p.xy())
    ext = p.extrude(Rectangle.from_center_and_sides(Point(s, 0, 0), 40, 20), 10)
    return p, ext


def _nodes(dag, op):
    types = {v: k for k, v in dag["serializableNodes"].items()}
    return [n for n in dag["DAG"].values() if types[n["type"]] == op]


def test_fillet_edges_accepts_position_radius_pairs():
    p, _ = block()
    f = p.fillet_edges(1.0, radius_end=2.0, radius_points=[(0.25, 3.0), (0.75, 1.5)])
    assert f.solid is None
    assert f.radius_end.value == 2.0
    assert [(pt.position.value, pt.radius.value) for pt in f.radius_points] == [
        (0.25, 3.0),
        (0.75, 1.5),
    ]


def test_radius_points_serialize_as_ordered_point_nodes():
    p, ext = block()
    p.add_operation(Fillet(ext, 1.0, radius_points=[FilletRadiusPoint(0.5, 4.0)]))
    dag = show_dag(p)
    (fillet,) = _nodes(dag, "Fillet")
    (pid,) = fillet["deps"]["radius_points"]
    point = dag["DAG"][pid]
    assert {
        dag["DAG"][point["deps"][k]]["params"]["value"] for k in ("position", "radius")
    } == {0.5, 4.0}


def test_part_fillet_on_a_solid_takes_radius_points():
    p, ext = block()
    f = p.fillet(ext, 2.0, radius_points=[(0.5, 1.0)])
    assert f.solid is ext and f.radius_points[0].radius.value == 1.0


@pytest.mark.parametrize("position", [0.0, 1.0, -0.2, 1.5])
def test_positions_must_lie_strictly_inside_the_edge(position):
    p, _ = block()
    with pytest.raises(ValueError, match="strictly between 0"):
        p.fillet_edges(1.0, radius_points=[(position, 2.0)])


def test_radii_must_be_positive():
    p, _ = block()
    with pytest.raises(ValueError, match="must be positive"):
        p.fillet_edges(1.0, radius_points=[(0.5, 0.0)])


def test_plain_fillet_edges_has_no_radius_points():
    p, _ = block()
    f = p.fillet_edges(1.0)
    assert f.radius_points is None and f.radius_end is None
