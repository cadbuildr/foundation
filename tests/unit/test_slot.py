"""Unit tests for the Slot family — SlotCenterToCenter,
SlotOverall and SlotCenterPoint."""

from cadbuildr.foundation.gen.models import (
    Part,
    Sketch,
    SlotCenterToCenter,
    SlotOverall,
    SlotCenterPoint,
    BoolParameter,
    Point,
    Extrusion,
)
from cadbuildr.foundation.dag_utils import show_dag


def test_slot_center_to_center_has_2_lines_and_2_arcs():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            slot = SlotCenterToCenter(Point(s, -10, 0), Point(s, 10, 0), height=4)
            self.add_operation(Extrusion(slot, end=2))

    dag = show_dag(_Part())
    serializable = dag["serializableNodes"]
    customs = [n for n in dag["DAG"].values() if n["type"] == serializable["CustomClosedShape"]]
    assert len(customs) == 1
    primitive_ids = customs[0]["deps"]["primitives"]
    types = [dag["DAG"][pid]["type"] for pid in primitive_ids]
    assert types.count(serializable["Line"]) == 2
    assert types.count(serializable["Arc"]) == 2


def test_slot_overall_expands_via_slot_center_to_center():
    """SlotOverall(width=20, height=4) should expand into a SlotCenterToCenter
    with endpoints at ±(width/2 - height/2) along sketch X — i.e. ±8."""

    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            slot = SlotOverall(s.origin, width=20, height=4)
            self.add_operation(Extrusion(slot, end=2))

    dag = show_dag(_Part())
    fp_type = dag["serializableNodes"]["FloatParameter"]
    fp_values = sorted(
        n["params"]["value"]
        for n in dag["DAG"].values()
        if n["type"] == fp_type and isinstance(n["params"].get("value"), (int, float))
    )
    # Endpoints x = ±(width/2 - height/2) = ±8.
    assert 8.0 in fp_values, f"Expected endpoint x=8; got {fp_values}"
    assert -8.0 in fp_values, f"Expected endpoint x=-8; got {fp_values}"


def test_slot_center_point_has_sketch_field():
    """SlotCenterPoint must expose a `sketch` field like its siblings.

    Without it, `get_extrusion_sketch` raised when the slot was used as an
    Extrusion shape — and building that ValueError's message repr'd a cyclic
    slot object, blowing the stack with a RecursionError. (This is what broke
    the documentation /Foundation/Parts/Primitives/slots page.)
    """
    assert "sketch" in SlotCenterPoint.model_fields
    s_part = type("_P", (Part,), {})()
    s = Sketch(s_part.xy())
    slot = SlotCenterPoint(center=Point(s, -10, 0), point=Point(s, 10, 0), height=4)
    # Resolves to the shared sketch (computed from `center.sketch`).
    assert slot.sketch is not None
    inner = slot.expand()
    assert isinstance(inner, SlotCenterToCenter)


def test_slots_doc_page_plate_serializes_without_recursion():
    """The documentation SlotsPlate mixes all three slot variants on one
    sketch. Serializing it must not recurse infinitely."""

    def cut(shape):
        return Extrusion(shape, end=4, cut=BoolParameter(value=True))

    class _Plate(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(cut(SlotCenterToCenter(Point(s, -25, 12), Point(s, 25, 12), height=4)))
            self.add_operation(cut(SlotOverall(Point(s, 0, 0), width=50, height=4)))
            self.add_operation(cut(SlotCenterPoint(center=Point(s, -25, -12), point=Point(s, 25, -12), height=4)))

    dag = show_dag(_Plate())
    serializable = dag["serializableNodes"]
    inv = {v: k for k, v in serializable.items()}
    type_names = [inv[n["type"]] for n in dag["DAG"].values()]
    # All three slots fully reduce to CustomClosedShape — no raw sugar nodes.
    assert "SlotCenterToCenter" not in type_names
    assert "SlotOverall" not in type_names
    assert "SlotCenterPoint" not in type_names
    assert type_names.count("CustomClosedShape") == 3
