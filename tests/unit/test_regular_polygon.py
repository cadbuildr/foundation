"""Unit tests for RegularPolygon."""

from cadbuildr.foundation.gen.models import Part, Sketch, RegularPolygon, Extrusion
from cadbuildr.foundation.dag_utils import show_dag


def test_regular_polygon_n_sides_appear_as_lines():
    """An n-gon should produce exactly n Lines after expansion."""

    class HeptPart(Part):
        def __init__(self):
            s = Sketch(self.xy())
            poly = RegularPolygon(s.origin, n_sides=7, radius=10)
            self.add_operation(Extrusion(poly, end=5))

    dag = show_dag(HeptPart())
    serializable = dag["serializableNodes"]
    line_type = serializable["Line"]
    polygons = [n for n in dag["DAG"].values() if n["type"] == serializable["Polygon"]]
    assert len(polygons) == 1, "RegularPolygon must expand to one Polygon"
    polygon = polygons[0]
    line_ids = polygon["deps"]["lines"]
    assert len(line_ids) == 7
    for lid in line_ids:
        assert dag["DAG"][lid]["type"] == line_type


def test_regular_polygon_5_sides():
    class PentPart(Part):
        def __init__(self):
            s = Sketch(self.xy())
            poly = RegularPolygon(s.origin, n_sides=5, radius=3)
            self.add_operation(Extrusion(poly, end=1))

    dag = show_dag(PentPart())
    polygons = [n for n in dag["DAG"].values() if n["type"] == dag["serializableNodes"]["Polygon"]]
    assert len(polygons) == 1
    assert len(polygons[0]["deps"]["lines"]) == 5
