"""Unit tests for the Cone composite primitive."""

from cadbuildr.foundation.gen.models import Part, Sketch, Cone
from cadbuildr.foundation.dag_utils import show_dag


def test_cone_expands_to_lathe():
    class ConePart(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Cone(s.origin, r1=10, r2=2, height=15))

    dag = show_dag(ConePart())
    serializable = dag["serializableNodes"]
    lathes = [n for n in dag["DAG"].values() if n["type"] == serializable["Lathe"]]
    assert len(lathes) == 1
    assert "Cone" not in serializable, "Cone must auto-expand"


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

    assert 10.0 in fp_values, f"Expected r1=10.0 corner X; got {fp_values}"
    assert 2.0 in fp_values, f"Expected r2=2.0 corner X; got {fp_values}"
    for y in (-7.0, 7.0):
        assert y in fp_values, f"Expected ±height/2 ({y}); got {fp_values}"
