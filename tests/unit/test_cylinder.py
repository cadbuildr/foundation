"""Unit tests for the Cylinder composite primitive."""

from cadbuildr.foundation.gen.models import Part, Sketch, Cylinder
from cadbuildr.foundation.dag_utils import show_dag


def test_cylinder_construction_and_expansion():
    """Cylinder(center, radius, height) should auto-expand into a Lathe."""

    class CylPart(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Cylinder(s.origin, radius=5, height=20))

    dag = show_dag(CylPart())
    serializable = dag["serializableNodes"]
    lathe_type = serializable["Lathe"]
    lathes = [n for n in dag["DAG"].values() if n["type"] == lathe_type]
    assert len(lathes) == 1, "Cylinder must expand to exactly one Lathe"
    assert "Cylinder" not in serializable, (
        "Cylinder must auto-expand at DAG time; no literal Cylinder type in registry"
    )


def test_cylinder_lathe_uses_polygon_profile_and_axis():
    """The Lathe inside a Cylinder should reference a Polygon profile and an Axis."""

    class CylPart(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Cylinder(s.origin, radius=3, height=10))

    dag = show_dag(CylPart())
    serializable = dag["serializableNodes"]
    polygon_type = serializable["Polygon"]
    axis_type = serializable["Axis"]

    lathes = [n for n in dag["DAG"].values() if n["type"] == serializable["Lathe"]]
    assert len(lathes) == 1
    lathe = lathes[0]

    shape_id = lathe["deps"]["shape"]
    axis_id = lathe["deps"]["axis"]
    assert dag["DAG"][shape_id]["type"] == polygon_type
    assert dag["DAG"][axis_id]["type"] == axis_type


def test_cylinder_dimensions_propagate():
    """radius should appear as a corner X coordinate; ±height/2 as corner Y coords."""

    class CylPart(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Cylinder(s.origin, radius=4.0, height=14.0))

    dag = show_dag(CylPart())
    fp_type = dag["serializableNodes"]["FloatParameter"]
    fp_values = sorted(
        n["params"]["value"]
        for n in dag["DAG"].values()
        if n["type"] == fp_type and isinstance(n["params"].get("value"), (int, float))
    )

    assert 4.0 in fp_values, f"Expected radius 4.0 as corner X; got {fp_values}"
    for y in (-7.0, 7.0):
        assert y in fp_values, f"Expected ±height/2 ({y}) as corner Y; got {fp_values}"
