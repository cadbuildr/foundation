"""Unit tests for the Cylinder composite primitive."""

from cadbuildr.foundation.gen.models import Part, Sketch, Cylinder
from cadbuildr.foundation.dag_utils import show_dag


def test_cylinder_construction_and_expansion():
    """Cylinder(center, radius, height) should auto-expand into an Extrusion."""

    class CylPart(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Cylinder(s.origin, radius=5, height=20))

    dag = show_dag(CylPart())
    serializable = dag["serializableNodes"]
    extrusion_type = serializable["Extrusion"]
    extrusions = [n for n in dag["DAG"].values() if n["type"] == extrusion_type]
    assert len(extrusions) == 1, "Cylinder must expand to exactly one Extrusion"
    assert "Cylinder" not in serializable, (
        "Cylinder must auto-expand at DAG time; no literal Cylinder type in registry"
    )


def test_cylinder_extrusion_uses_circle_profile():
    """The Extrusion inside a Cylinder should reference a Circle shape."""

    class CylPart(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Cylinder(s.origin, radius=3, height=10))

    dag = show_dag(CylPart())
    serializable = dag["serializableNodes"]
    circle_type = serializable["Circle"]
    extrusion_type = serializable["Extrusion"]

    extrusions = [n for n in dag["DAG"].values() if n["type"] == extrusion_type]
    assert len(extrusions) == 1
    extrusion = extrusions[0]

    shape_ids = extrusion["deps"].get("shape", [])
    assert len(shape_ids) == 1
    assert dag["DAG"][shape_ids[0]]["type"] == circle_type, (
        "Cylinder's extruded shape should be a Circle"
    )


def test_cylinder_dimensions_propagate():
    """radius and ±height/2 should appear in the DAG as FloatParameter values."""

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

    assert 4.0 in fp_values, f"Expected radius 4.0 in DAG; got {fp_values}"
    for z in (-7.0, 7.0):
        assert z in fp_values, f"Expected ±height/2 ({z}) as start/end; got {fp_values}"
