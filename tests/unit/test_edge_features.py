"""Part.fillet_edges / Part.chamfer_edges: CAD-style edge features on the
part's body (a Fillet / Chamfer with no ``solid``)."""

import pytest

from cadbuildr.foundation import (
    Chamfer,
    EdgeFinder,
    Extrusion,
    Fillet,
    ParallelToAxisRule,
    Part,
    Point,
    Rectangle,
    Sketch,
)
from cadbuildr.foundation.dag_utils import show_dag


def block():
    p = Part()
    s = Sketch(p.xy())
    ext = p.extrude(Rectangle.from_center_and_sides(Point(s, 0, 0), 20, 20), 5)
    return p, ext


def _node(dag, op):
    types = {v: k for k, v in dag["serializableNodes"].items()}
    return [n for n in dag["DAG"].values() if types[n["type"]] == op]


def test_fillet_edges_adds_a_solidless_fillet():
    p, _ = block()
    f = p.fillet_edges(1.0)
    assert isinstance(f, Fillet) and f.solid is None
    assert p.operations[-1] is f
    (node,) = _node(show_dag(p), "Fillet")
    assert "solid" not in node["deps"]


def test_chamfer_edges_keeps_the_selector():
    p, _ = block()
    finder = EdgeFinder(ParallelToAxisRule("Z"))
    c = p.chamfer_edges(0.5, edges=finder)
    assert isinstance(c, Chamfer) and c.solid is None and c.edge_finder is finder


@pytest.mark.parametrize("method", ["fillet_edges", "chamfer_edges"])
def test_edge_feature_on_an_empty_part_is_an_error(method):
    with pytest.raises(ValueError, match="before"):
        getattr(Part(), method)(1.0)


def test_fillet_of_a_solid_is_unchanged():
    p, ext = block()
    f = Fillet(ext, 1.0)
    assert f.solid is ext and f.radius.value == 1.0
    assert p.fillet(ext, 1.0).solid is ext
    assert isinstance(ext, Extrusion)
