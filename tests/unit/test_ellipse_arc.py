from cadbuildr.foundation import (
    Arc,
    CustomClosedShape,
    EllipseArc,
    Extrusion,
    FloatParameter,
    Part,
    Point,
    Sketch,
)
from cadbuildr.foundation.dag_utils import show_dag


def test_ellipse_arc_registers_to_sketch_and_shape_union():
    part = Part()
    sketch = Sketch(part.xy())
    ellipse_arc = EllipseArc(
        center=Point(sketch, 0.0, 0.0),
        a=FloatParameter(value=20.0),
        b=FloatParameter(value=10.0),
        start_angle=FloatParameter(value=0.0),
        end_angle=FloatParameter(value=3.141592653589793),
    )
    closing_line = Arc.from_two_points_and_radius(
        Point(sketch, 20.0, 0.0),
        Point(sketch, -20.0, 0.0),
        FloatParameter(value=40.0),
    )
    if closing_line is None:
        raise AssertionError("Expected Arc.from_two_points_and_radius to produce an Arc")

    shape = CustomClosedShape([ellipse_arc, closing_line])
    part.add_operation(Extrusion(shape, 5.0))

    dag = show_dag(part)
    serializable = dag["serializableNodes"]
    ellipse_arc_type = serializable.get("EllipseArc")
    assert ellipse_arc_type is not None, "EllipseArc type was not registered in serializableNodes"
    ellipse_arc_nodes = [
        node for node in dag["DAG"].values() if node["type"] == ellipse_arc_type
    ]
    assert len(ellipse_arc_nodes) == 1

    ellipse_arc_node = ellipse_arc_nodes[0]
    assert "center" in ellipse_arc_node["deps"]
    assert "a" in ellipse_arc_node["deps"]
    assert "b" in ellipse_arc_node["deps"]
    assert "start_angle" in ellipse_arc_node["deps"]
    assert "end_angle" in ellipse_arc_node["deps"]
