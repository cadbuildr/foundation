"""Unit tests for Wedge — schema landed; kernel binding deferred."""

from cadbuildr.foundation.gen.models import Part, Sketch, Wedge
from cadbuildr.foundation.dag_utils import show_dag


def test_wedge_persists_as_native_dag_node():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Wedge(s.origin, dx=10, dy=8, dz=6, ltx=4))

    dag = show_dag(_Part())
    assert "Wedge" in dag["serializableNodes"]
    wedges = [n for n in dag["DAG"].values() if n["type"] == dag["serializableNodes"]["Wedge"]]
    assert len(wedges) == 1


def test_wedge_dimensions_round_trip():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Wedge(s.origin, dx=12, dy=8, dz=6, ltx=4))

    dag = show_dag(_Part())
    fp_type = dag["serializableNodes"]["FloatParameter"]
    fp_values = sorted(
        n["params"]["value"]
        for n in dag["DAG"].values()
        if n["type"] == fp_type and isinstance(n["params"].get("value"), (int, float))
    )
    for expected in (12.0, 8.0, 6.0, 4.0):
        assert expected in fp_values
