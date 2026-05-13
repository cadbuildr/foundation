"""Unit tests for Offset2D."""

from cadbuildr.foundation.gen.models import (
    Part,
    Sketch,
    Circle,
    Offset2D,
    Extrusion,
)
from cadbuildr.foundation.dag_utils import show_dag


def test_offset2d_persists_as_native_dag_node():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            inner = Circle(s.origin, radius=5)
            offset = Offset2D(shape=inner, distance=2)
            self.add_operation(Extrusion(offset, end=3))

    dag = show_dag(_Part())
    assert "Offset2D" in dag["serializableNodes"]
    offsets = [n for n in dag["DAG"].values() if n["type"] == dag["serializableNodes"]["Offset2D"]]
    assert len(offsets) == 1
    # The Offset's `shape` dep should reference the inner Circle.
    inner_id = offsets[0]["deps"]["shape"]
    assert dag["DAG"][inner_id]["type"] == dag["serializableNodes"]["Circle"]
