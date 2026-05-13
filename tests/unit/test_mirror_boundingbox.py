"""Unit tests for Mirror + BoundingBox — native nodes."""

from cadbuildr.foundation.gen.models import (
    Part,
    Sketch,
    Box,
    Sphere,
    Mirror,
    BoundingBox,
)
from cadbuildr.foundation.dag_utils import show_dag


def test_mirror_persists_as_native_dag_node():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            box = Box(s.origin, w=10, h=10, d=10)
            self.add_operation(box)
            # Mirror requires a SolidOperation (not Box, since Box @expands).
            # We use the box directly through.expand to get the Extrusion.
            self.add_operation(Mirror(shape=box.expand(), plane_name="XZ"))

    dag = show_dag(_Part())
    assert "Mirror" in dag["serializableNodes"]
    mirrors = [n for n in dag["DAG"].values() if n["type"] == dag["serializableNodes"]["Mirror"]]
    assert len(mirrors) == 1


def test_bounding_box_persists_as_native_dag_node():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            sphere = Sphere(s.origin, radius=5)
            self.add_operation(sphere)
            self.add_operation(BoundingBox(shape=sphere))

    dag = show_dag(_Part())
    assert "BoundingBox" in dag["serializableNodes"]
    bbs = [n for n in dag["DAG"].values() if n["type"] == dag["serializableNodes"]["BoundingBox"]]
    assert len(bbs) == 1
