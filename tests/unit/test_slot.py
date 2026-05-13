"""Unit tests for the Slot family — SlotCenterToCenter
and SlotOverall as the canonical pair; SlotCenterPoint and SlotArc are
tracked as follow-ups."""

from cadbuildr.foundation.gen.models import (
    Part,
    Sketch,
    SlotCenterToCenter,
    SlotOverall,
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
