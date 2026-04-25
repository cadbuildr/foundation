from cadbuildr.foundation import (  # pragma: allowlist secret
    Circle,
    Extrusion,
    Line,
    Part,
    Point,
    Polygon,
    Sketch,
)
from cadbuildr.foundation.dag_utils import show_dag  # pragma: allowlist secret


def _assert_vector_close(actual, expected, tol=1e-9):
    assert len(actual) == len(expected)
    for i, exp in enumerate(expected):
        assert abs(actual[i] - exp) < tol, f"component {i}: expected {exp}, got {actual[i]}"


def test_line_get_extrusion_plane_axes_and_origin():
    part = Part()
    sketch = Sketch(part.xy())
    line = Line(Point(sketch, 1.0, 2.0), Point(sketch, 4.0, 2.0))

    plane = line.get_extrusion_plane(extrusion_direction=[0.0, 0.0, 1.0], name="edge_plane")

    assert plane.frame.top_frame == sketch.plane.frame
    _assert_vector_close(plane.frame.position, [1.0, 2.0, 0.0])
    _assert_vector_close(plane.get_x_axis(), [1.0, 0.0, 0.0])
    _assert_vector_close(plane.get_y_axis(), [0.0, 0.0, 1.0])
    _assert_vector_close(plane.get_z_axis(), [0.0, -1.0, 0.0])


def test_line_extrusion_plane_shortcut_matches_schema_method():
    part = Part()
    sketch = Sketch(part.xy())
    line = Line(Point(sketch, 0.0, 0.0), Point(sketch, 0.0, 10.0))

    plane_from_method = line.get_extrusion_plane(
        extrusion_direction=[0.0, 0.0, 1.0],
        name="method_plane",
    )
    plane_from_shortcut = line.extrusion_plane(
        extrusion_direction=[0.0, 0.0, 1.0],
        name="shortcut_plane",
    )

    _assert_vector_close(plane_from_method.frame.position, plane_from_shortcut.frame.position)
    _assert_vector_close(plane_from_method.get_x_axis(), plane_from_shortcut.get_x_axis())
    _assert_vector_close(plane_from_method.get_y_axis(), plane_from_shortcut.get_y_axis())
    _assert_vector_close(plane_from_method.get_z_axis(), plane_from_shortcut.get_z_axis())


def test_line_extrusion_plane_cube_with_side_cylinders_builds():
    part = Part()
    cube_size = 20.0

    base_sketch = Sketch(part.xy())
    p1 = Point(base_sketch, 0.0, 0.0)
    p2 = Point(base_sketch, cube_size, 0.0)
    p3 = Point(base_sketch, cube_size, cube_size)
    p4 = Point(base_sketch, 0.0, cube_size)
    square = Polygon([Line(p1, p2), Line(p2, p3), Line(p3, p4), Line(p4, p1)])
    part.add_operation(Extrusion(square, cube_size))

    side_edges = [
        Line(Point(base_sketch, 0.0, 0.0), Point(base_sketch, cube_size, 0.0)),
        Line(Point(base_sketch, cube_size, 0.0), Point(base_sketch, cube_size, cube_size)),
        Line(Point(base_sketch, cube_size, cube_size), Point(base_sketch, 0.0, cube_size)),
        Line(Point(base_sketch, 0.0, cube_size), Point(base_sketch, 0.0, 0.0)),
    ]
    for edge in side_edges:
        side_sketch = Sketch(
            edge.extrusion_plane(extrusion_direction=[0.0, 0.0, 1.0], name="side")
        )
        part.add_operation(Extrusion(Circle(Point(side_sketch, 10.0, 10.0), 2.0), 3.0))

    dag = show_dag(part)
    extrusion_type = dag["serializableNodes"]["Extrusion"]
    extrusion_nodes = [node for node in dag["DAG"].values() if node["type"] == extrusion_type]

    assert len(extrusion_nodes) == 5
    assert all("sketch" in node.get("deps", {}) for node in extrusion_nodes)
