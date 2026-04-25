from cadbuildr.foundation import Part, Sketch, Point, Spline
from cadbuildr.foundation.dag_utils import show_dag


def test_spline_auto_registered_and_serialized():
    part = Part()
    sketch = Sketch(part.xy())

    p1 = Point(sketch, 0.0, 0.0)
    p2 = Point(sketch, 0.5, 0.1)
    p3 = Point(sketch, 1.0, 0.0)

    spline = Spline([p1, p2, p3])
    assert spline in sketch.elements

    dag = show_dag(sketch)
    serializable_nodes = dag["serializableNodes"]
    spline_type_id = serializable_nodes["Spline"]

    spline_nodes = [node for node in dag["DAG"].values() if node["type"] == spline_type_id]
    assert len(spline_nodes) == 1
    assert len(spline_nodes[0]["deps"]["points"]) == 3
