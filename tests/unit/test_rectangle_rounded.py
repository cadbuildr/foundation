"""Unit tests for RectangleRounded."""

import pytest

from cadbuildr.foundation.gen.models import Part, Sketch, RectangleRounded, Extrusion
from cadbuildr.foundation.dag_utils import show_dag


def test_rectangle_rounded_expands_to_custom_closed_shape():
    class RRPart(Part):
        def __init__(self):
            s = Sketch(self.xy())
            shape = RectangleRounded(s.origin, w=20, h=10, radius=2)
            self.add_operation(Extrusion(shape, end=4))

    dag = show_dag(RRPart())
    serializable = dag["serializableNodes"]
    ccs_type = serializable["CustomClosedShape"]
    line_type = serializable["Line"]
    arc_type = serializable["Arc"]
    customs = [n for n in dag["DAG"].values() if n["type"] == ccs_type]
    assert len(customs) == 1
    primitive_ids = customs[0]["deps"]["primitives"]
    primitive_types = [dag["DAG"][pid]["type"] for pid in primitive_ids]
    # 4 lines + 4 arcs alternating.
    assert primitive_types.count(line_type) == 4
    assert primitive_types.count(arc_type) == 4


def test_rectangle_rounded_rejects_oversized_radius():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            shape = RectangleRounded(s.origin, w=10, h=4, radius=3)
            self.add_operation(Extrusion(shape, end=1))

    with pytest.raises(ValueError, match="cannot exceed"):
        show_dag(_Part())
