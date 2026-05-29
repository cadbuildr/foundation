"""Cut-field plumbing for Box / Cylinder / Sphere.

Box and Cylinder both @expand into Extrusion; the cut flag must propagate
through the expansion. Sphere is native and exposes the field directly.
PartRoot consumes `.cut` on each operation node to choose fuse vs. cut at
part-build time, so all three primitives can act as subtractive operations
once they ship cut=True."""

from cadbuildr.foundation.gen.models import (
    Part, Sketch, Box, Cylinder, Sphere, BoolParameter,
)
from cadbuildr.foundation.dag_utils import show_dag


def _dag_has_type(dag: dict, type_name: str) -> bool:
    type_id = dag["serializableNodes"].get(type_name)
    if type_id is None:
        return False
    return any(n["type"] == type_id for n in dag["DAG"].values())


def _bool_values_in_dag(dag: dict) -> list[bool]:
    bp_type = dag["serializableNodes"].get("BoolParameter")
    if bp_type is None:
        return []
    return [
        n["params"]["value"]
        for n in dag["DAG"].values()
        if n["type"] == bp_type and "value" in n.get("params", {})
    ]


def test_box_default_cut_is_false():
    class P(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Box(center=s.origin, w=10, h=10, d=10))

    dag = show_dag(P())
    # Box → Extrusion. The Extrusion's cut should default to False.
    assert _dag_has_type(dag, "Extrusion")
    bools = _bool_values_in_dag(dag)
    assert False in bools, f"Expected default cut=False in DAG; got {bools}"
    assert True not in bools


def test_box_with_cut_true_propagates_to_extrusion():
    """Box(cut=True) → its expanded Extrusion must carry cut=True."""

    class P(Part):
        def __init__(self):
            s = Sketch(self.xy())
            big = Box(center=s.origin, w=10, h=10, d=10)
            small = Box(
                center=s.origin, w=4, h=4, d=4,
                cut=BoolParameter(value=True),
            )
            self.add_operation(big)
            self.add_operation(small)

    dag = show_dag(P())
    bools = _bool_values_in_dag(dag)
    # The big Box defaults to False, the small one passes True.
    assert True in bools, f"Expected cut=True in DAG from cutting Box; got {bools}"
    assert False in bools


def test_cylinder_with_cut_true_propagates_to_extrusion():
    """Cylinder(cut=True) → its expanded Extrusion must carry cut=True."""

    class P(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Box(center=s.origin, w=10, d=10, h=10))
            self.add_operation(
                Cylinder(
                    center=s.origin, radius=2, height=10,
                    cut=BoolParameter(value=True),
                )
            )

    dag = show_dag(P())
    assert _dag_has_type(dag, "Extrusion")
    assert True in _bool_values_in_dag(dag)


def test_sphere_with_cut_true_keeps_cut_in_dag():
    """Sphere is native — `cut: BoolParameter` lands directly on the DAG node."""

    class P(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Box(center=s.origin, w=10, h=10, d=10))
            self.add_operation(
                Sphere(
                    center=s.origin, radius=3,
                    cut=BoolParameter(value=True),
                )
            )

    dag = show_dag(P())
    # Sphere stays in the DAG (no @expand), so we can find it directly.
    assert _dag_has_type(dag, "Sphere")
    sphere_type_id = dag["serializableNodes"]["Sphere"]
    sphere_nodes = [n for n in dag["DAG"].values() if n["type"] == sphere_type_id]
    assert len(sphere_nodes) == 1
    cut_dep = sphere_nodes[0]["deps"].get("cut")
    assert cut_dep is not None, (
        "Sphere DAG node must carry a 'cut' dependency once the field is wired"
    )
    cut_node = dag["DAG"][cut_dep]
    assert cut_node["params"]["value"] is True


def test_sphere_default_cut_field_present_and_false():
    """Defaulting (no explicit cut arg) should still emit the BoolParameter
    so the kernel can read it without nullable handling."""

    class P(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Sphere(center=s.origin, radius=3))

    dag = show_dag(P())
    sphere_type_id = dag["serializableNodes"]["Sphere"]
    sphere_nodes = [n for n in dag["DAG"].values() if n["type"] == sphere_type_id]
    assert len(sphere_nodes) == 1
    cut_dep = sphere_nodes[0]["deps"].get("cut")
    assert cut_dep is not None, "default cut should still emit a node"
    assert dag["DAG"][cut_dep]["params"]["value"] is False
