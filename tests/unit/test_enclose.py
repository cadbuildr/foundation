"""Enclose: a solid from surfaces that cross and overhang each other."""

import pytest

from cadbuildr.foundation import (
    Enclose,
    Extrusion,
    Part,
    PlanarSurface,
    Rectangle,
    Sketch,
)
from cadbuildr.foundation.dag_utils import show_dag


def _sheet(plane, offset, size=60):
    s = Sketch(plane.get_parallel_plane(offset))
    return PlanarSurface(Rectangle.from_center_and_sides(s.origin, size, size))


def test_enclose_persists_with_every_surface_as_a_dependency():
    p = Part()
    sheets = [
        _sheet(p.xy(), -5),
        _sheet(p.xy(), 5),
        _sheet(p.yz(), -15),
        _sheet(p.yz(), 15),
        _sheet(p.xz(), -10),
        _sheet(p.xz(), 10),
    ]
    p.add_operation(Enclose(sheets))
    dag = show_dag(p)

    type_name = {v: k for k, v in dag["serializableNodes"].items()}
    nodes = dag["DAG"]
    enclose = [n for n in nodes.values() if type_name[n["type"]] == "Enclose"]
    assert len(enclose) == 1
    surface_ids = enclose[0]["deps"]["surfaces"]
    assert len(surface_ids) == 6
    assert {type_name[nodes[i]["type"]] for i in surface_ids} == {"PlanarSurface"}


def test_enclose_takes_surfaces_not_solids():
    p = Part()
    s = Sketch(p.xy())
    solid = Extrusion(Rectangle.from_center_and_sides(s.origin, 10, 10), 5)
    with pytest.raises(Exception):
        Enclose([solid])
