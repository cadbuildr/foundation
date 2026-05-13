"""Unit tests for the Box composite primitive."""

from cadbuildr.foundation.gen.models import Part, Sketch, Box
from cadbuildr.foundation.dag_utils import pydantic_to_dag, show_dag
from cadbuildr.foundation.foundation_hooks import setup_foundation_hooks


def test_box_construction_and_expansion():
    """Box(center, w, h, d) should auto-expand into an Extrusion at DAG time."""

    class BoxPart(Part):
        def __init__(self, w=10, h=20, d=30):
            s = Sketch(self.xy())
            box = Box(s.origin, w=w, h=h, d=d)
            self.add_operation(box)

    part = BoxPart()
    memo = {}
    type_registry = {}
    hooks = setup_foundation_hooks()
    pydantic_to_dag(part, memo=memo, type_registry=type_registry, hooks=hooks)

    # Box is not in DEFAULT_VALID_TYPES, so it must auto-expand to Extrusion.
    extrusion_nodes = [
        n for n in memo.values() if n["type"] == type_registry.get("Extrusion")
    ]
    assert len(extrusion_nodes) >= 1, "Box should expand into at least one Extrusion node"
    assert "Box" not in type_registry, (
        "Box must auto-expand at DAG time; the literal Box type should not appear in the registry"
    )


def test_box_extrusion_shape_is_rectangle():
    """The expanded Extrusion's shape must be a Rectangle/Polygon (closed)."""

    class BoxPart(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Box(s.origin, w=10, h=20, d=30))

    dag = show_dag(BoxPart())
    serializable = dag["serializableNodes"]
    extrusion_type = serializable["Extrusion"]

    extrusions = [n for n in dag["DAG"].values() if n["type"] == extrusion_type]
    assert len(extrusions) == 1, "Box should expand to exactly one Extrusion"

    # Box → RectangleFromCenterAndSides → Rectangle. Rectangle is in
    # DEFAULT_VALID_TYPES so it persists in the DAG (the further expansion
    # to Polygon would only happen if Rectangle were not a valid type).
    rectangle_type = serializable["Rectangle"]
    extrusion = extrusions[0]
    shape_ids = extrusion["deps"].get("shape", [])
    assert len(shape_ids) == 1
    shape_node = dag["DAG"][shape_ids[0]]
    assert shape_node["type"] == rectangle_type, (
        f"Box's extruded shape should be a Rectangle, got type id {shape_node['type']}"
    )


def test_box_dimensions_propagate_into_dag():
    """Box dimensions should reach the DAG: depth as Extrusion.end, width/height
    as the corner offsets of the underlying Rectangle (RectangleFromCenterAndSides
    consumes w/h to produce ±w/2, ±h/2 corner coordinates)."""

    class BoxPart(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Box(s.origin, w=12.5, h=7.0, d=42.0))

    dag = show_dag(BoxPart())
    fp_type = dag["serializableNodes"]["FloatParameter"]
    fp_values = sorted(
        n["params"]["value"]
        for n in dag["DAG"].values()
        if n["type"] == fp_type and isinstance(n["params"].get("value"), (int, float))
    )

    # Depth lands directly on Extrusion.end.
    assert 42.0 in fp_values, f"Expected depth 42.0 in DAG; got {fp_values}"
    # w=12.5 → ±6.25 and h=7.0 → ±3.5 on the four rectangle corners.
    assert 6.25 in fp_values and -6.25 in fp_values, (
        f"Expected ±w/2 (±6.25) corner coords from w=12.5; got {fp_values}"
    )
    assert 3.5 in fp_values and -3.5 in fp_values, (
        f"Expected ±h/2 (±3.5) corner coords from h=7.0; got {fp_values}"
    )
