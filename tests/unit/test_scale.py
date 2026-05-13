"""Unit tests for Scale — uniform scale only."""

from cadbuildr.foundation.gen.models import Part, Sketch, Sphere, Scale
from cadbuildr.foundation.dag_utils import show_dag


def test_scale_persists_as_native_dag_node():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            sphere = Sphere(s.origin, radius=1)
            self.add_operation(sphere)
            self.add_operation(Scale(shape=sphere, factor=2.0))

    dag = show_dag(_Part())
    assert "Scale" in dag["serializableNodes"]
    scales = [n for n in dag["DAG"].values() if n["type"] == dag["serializableNodes"]["Scale"]]
    assert len(scales) == 1
