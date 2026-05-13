"""Unit tests for Torus."""

from cadbuildr.foundation.gen.models import Part, Sketch, Torus
from cadbuildr.foundation.dag_utils import show_dag


def test_torus_expands_to_lathe_of_circle():
    class TorusPart(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Torus(s.origin, major_radius=20, minor_radius=5))

    dag = show_dag(TorusPart())
    serializable = dag["serializableNodes"]
    lathes = [n for n in dag["DAG"].values() if n["type"] == serializable["Lathe"]]
    circles = [n for n in dag["DAG"].values() if n["type"] == serializable["Circle"]]
    assert len(lathes) == 1
    assert len(circles) == 1, "Torus profile must be a single Circle"
    assert "Torus" not in serializable, "Torus must auto-expand"
