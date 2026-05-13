"""Unit tests for Section / Split / Project (, , ) —
schema landed; kernel bindings deferred."""

from cadbuildr.foundation.gen.models import (
    Part,
    Sketch,
    Sphere,
    Section,
    Split,
    Project,
)
from cadbuildr.foundation.dag_utils import show_dag


def test_section_persists_as_native_dag_node():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            sphere = Sphere(s.origin, radius=5)
            self.add_operation(sphere)
            self.add_operation(Section(shape := sphere, plane_name="XY"))

    dag = show_dag(_Part())
    assert "Section" in dag["serializableNodes"]


def test_split_persists_as_native_dag_node():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            sphere = Sphere(s.origin, radius=5)
            self.add_operation(sphere)
            self.add_operation(Split(solid=sphere, plane_name="XY", keep="TOP"))

    dag = show_dag(_Part())
    assert "Split" in dag["serializableNodes"]


def test_project_persists_as_native_dag_node():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            sphere = Sphere(s.origin, radius=5)
            self.add_operation(sphere)
            self.add_operation(Project(shape=sphere, target_plane_name="XY"))

    dag = show_dag(_Part())
    assert "Project" in dag["serializableNodes"]
