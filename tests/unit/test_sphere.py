"""Unit tests for Sphere — native node."""

from cadbuildr.foundation.gen.models import Part, Sketch, Sphere
from cadbuildr.foundation.dag_utils import show_dag


def test_sphere_persists_as_native_dag_node():
    """Sphere is in DEFAULT_VALID_TYPES, so it must NOT auto-expand at DAG time —
    it appears as a `Sphere` node and the kernel handler dispatches via
    SphereReplicad → factory.createSphere."""

    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Sphere(s.origin, radius=10))

    dag = show_dag(_Part())
    serializable = dag["serializableNodes"]
    assert "Sphere" in serializable, (
        "Sphere must appear in the type registry — it's a native node, not @expand"
    )
    spheres = [n for n in dag["DAG"].values() if n["type"] == serializable["Sphere"]]
    assert len(spheres) == 1


def test_sphere_radius_lands_as_dependency():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Sphere(s.origin, radius=7.5))

    dag = show_dag(_Part())
    sphere = next(n for n in dag["DAG"].values() if n["type"] == dag["serializableNodes"]["Sphere"])
    radius_id = sphere["deps"]["radius"]
    radius_node = dag["DAG"][radius_id]
    assert radius_node["params"]["value"] == 7.5
