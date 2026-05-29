"""Unit tests for the Cone composite primitive."""

from cadbuildr.foundation.gen.models import Part, Sketch, Cone
from cadbuildr.foundation.dag_utils import show_dag


def test_cone_expands_to_extrusion():
    class ConePart(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Cone(s.origin, r1=10, r2=2, height=15))

    dag = show_dag(ConePart())
    serializable = dag["serializableNodes"]
    extrusions = [n for n in dag["DAG"].values() if n["type"] == serializable["Extrusion"]]
    assert len(extrusions) == 1
    assert "Cone" not in serializable, "Cone must auto-expand"


def test_cone_extrusion_uses_circle_profile():
    class ConePart(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Cone(s.origin, r1=10, r2=2, height=15))

    dag = show_dag(ConePart())
    serializable = dag["serializableNodes"]
    extrusion_type = serializable["Extrusion"]
    circle_type = serializable["Circle"]

    extrusions = [n for n in dag["DAG"].values() if n["type"] == extrusion_type]
    assert len(extrusions) == 1
    shape_ids = extrusions[0]["deps"].get("shape", [])
    assert len(shape_ids) == 1
    assert dag["DAG"][shape_ids[0]]["type"] == circle_type, (
        "Cone's extruded shape should be a Circle"
    )


def test_cone_radii_and_height_appear_in_dag():
    class ConePart(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Cone(s.origin, r1=10.0, r2=2.0, height=14.0))

    dag = show_dag(ConePart())
    fp_type = dag["serializableNodes"]["FloatParameter"]
    fp_values = sorted(
        n["params"]["value"]
        for n in dag["DAG"].values()
        if n["type"] == fp_type and isinstance(n["params"].get("value"), (int, float))
    )

    assert 10.0 in fp_values, f"Expected r1=10.0; got {fp_values}"
    for z in (-7.0, 7.0):
        assert z in fp_values, f"Expected ±height/2 ({z}); got {fp_values}"


def test_cone_taper_value():
    """taper_val = (r1 - r2) / r1 should appear in the DAG."""

    class ConePart(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Cone(s.origin, r1=10.0, r2=2.0, height=14.0))

    dag = show_dag(ConePart())
    fp_type = dag["serializableNodes"]["FloatParameter"]
    fp_values = sorted(
        n["params"]["value"]
        for n in dag["DAG"].values()
        if n["type"] == fp_type and isinstance(n["params"].get("value"), (int, float))
    )

    expected_taper = (10.0 - 2.0) / 10.0  # 0.8
    assert any(abs(v - expected_taper) < 1e-9 for v in fp_values), (
        f"Expected taper_val={(10.0-2.0)/10.0:.6f}; got {fp_values}"
    )
