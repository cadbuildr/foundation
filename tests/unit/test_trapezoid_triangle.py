"""Unit tests for Trapezoid and Triangle."""

from cadbuildr.foundation.gen.models import Part, Sketch, Trapezoid, Triangle, Point, Extrusion
from cadbuildr.foundation.dag_utils import show_dag


def test_trapezoid_expands_to_polygon_of_4_lines():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Extrusion(Trapezoid(s.origin, w_top=10, w_bottom=20, h=8), end=2))

    dag = show_dag(_Part())
    polygons = [n for n in dag["DAG"].values() if n["type"] == dag["serializableNodes"]["Polygon"]]
    assert len(polygons) == 1
    assert len(polygons[0]["deps"]["lines"]) == 4


def test_triangle_expands_to_polygon_of_3_lines():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            t = Triangle(Point(s, 0, 0), Point(s, 10, 0), Point(s, 5, 8))
            self.add_operation(Extrusion(t, end=1))

    dag = show_dag(_Part())
    polygons = [n for n in dag["DAG"].values() if n["type"] == dag["serializableNodes"]["Polygon"]]
    assert len(polygons) == 1
    assert len(polygons[0]["deps"]["lines"]) == 3
