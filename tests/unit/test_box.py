"""Unit tests for the Box composite primitive."""

from cadbuildr.foundation.gen.models import Part, Sketch, Box
from cadbuildr.foundation.dag_utils import pydantic_to_dag, show_dag
from cadbuildr.foundation.foundation_hooks import setup_foundation_hooks


def test_box_construction_and_expansion():
    """Box(center, w, d, h) should auto-expand into an Extrusion at DAG time."""

    class BoxPart(Part):
        def __init__(self, w=10, d=20, h=30):
            s = Sketch(self.xy())
            box = Box(s.origin, w=w, d=d, h=h)
            self.add_operation(box)

    part = BoxPart()
    memo = {}
    type_registry = {}
    hooks = setup_foundation_hooks()
    pydantic_to_dag(part, memo=memo, type_registry=type_registry, hooks=hooks)

    extrusion_nodes = [
        n for n in memo.values() if n["type"] == type_registry.get("Extrusion")
    ]
    assert len(extrusion_nodes) >= 1, "Box should expand into at least one Extrusion node"
    assert "Box" not in type_registry, (
        "Box must auto-expand at DAG time; the literal Box type should not appear in the registry"
    )


def test_box_extrusion_shape_is_rectangle():
    """The expanded Extrusion's shape must be a Rectangle."""

    class BoxPart(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Box(s.origin, w=10, d=20, h=30))

    dag = show_dag(BoxPart())
    serializable = dag["serializableNodes"]
    extrusion_type = serializable["Extrusion"]

    extrusions = [n for n in dag["DAG"].values() if n["type"] == extrusion_type]
    assert len(extrusions) == 1, "Box should expand to exactly one Extrusion"

    rectangle_type = serializable["Rectangle"]
    extrusion = extrusions[0]
    shape_ids = extrusion["deps"].get("shape", [])
    assert len(shape_ids) == 1
    shape_node = dag["DAG"][shape_ids[0]]
    assert shape_node["type"] == rectangle_type, (
        f"Box's extruded shape should be a Rectangle, got type id {shape_node['type']}"
    )


def test_box_dimensions_propagate_into_dag():
    """Box dimensions should reach the DAG: h as Extrusion ±start/end, w and d
    as corner offsets of the underlying Rectangle."""

    class BoxPart(Part):
        def __init__(self):
            s = Sketch(self.xy())
            # w=12.5 (X), d=7.0 (Y), h=42.0 (Z / sketch normal)
            self.add_operation(Box(s.origin, w=12.5, d=7.0, h=42.0))

    dag = show_dag(BoxPart())
    fp_type = dag["serializableNodes"]["FloatParameter"]
    fp_values = sorted(
        n["params"]["value"]
        for n in dag["DAG"].values()
        if n["type"] == fp_type and isinstance(n["params"].get("value"), (int, float))
    )

    # h=42.0 → ±21.0 as Extrusion start/end (box is centered on Z).
    assert 21.0 in fp_values and -21.0 in fp_values, (
        f"Expected ±h/2 (±21.0) as start/end from h=42.0; got {fp_values}"
    )
    # w=12.5 → ±6.25 as Rectangle corner X offsets.
    assert 6.25 in fp_values and -6.25 in fp_values, (
        f"Expected ±w/2 (±6.25) corner coords from w=12.5; got {fp_values}"
    )
    # d=7.0 → ±3.5 as Rectangle corner Y offsets.
    assert 3.5 in fp_values and -3.5 in fp_values, (
        f"Expected ±d/2 (±3.5) corner coords from d=7.0; got {fp_values}"
    )
