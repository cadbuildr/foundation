"""Unit tests for FinderRule expansion + SortByRule."""

from cadbuildr.foundation.gen.models import (
    EdgeFinder,
    Fillet,
    Part,
    Sketch,
    Box,
    IsCircleRule,
    OfTypeRule,
    LengthRangeRule,
    RadiusRangeRule,
    ParallelToAxisRule,
    OnFaceRule,
    SortByRule,
    StringParameter,
)
from cadbuildr.foundation.dag_utils import show_dag


def _part_with_finder(rule):
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            box = Box(s.origin, w=10, h=10, d=10)
            self.add_operation(box)
            ef = EdgeFinder(rule=rule)
            self.add_operation(Fillet(box.expand(), radius=0.5, edge_finder=ef))

    return _Part()


def test_is_circle_rule_round_trips():
    dag = show_dag(_part_with_finder(IsCircleRule()))
    assert "IsCircleRule" in dag["serializableNodes"]


def test_of_type_rule_round_trips():
    dag = show_dag(_part_with_finder(OfTypeRule(type_name=StringParameter(value="LINE"))))
    assert "OfTypeRule" in dag["serializableNodes"]


def test_length_range_rule_round_trips():
    dag = show_dag(_part_with_finder(LengthRangeRule(min=1.0, max=10.0)))
    assert "LengthRangeRule" in dag["serializableNodes"]


def test_radius_range_rule_round_trips():
    dag = show_dag(_part_with_finder(RadiusRangeRule(min=2.0, max=5.0)))
    assert "RadiusRangeRule" in dag["serializableNodes"]


def test_parallel_to_axis_rule_round_trips():
    dag = show_dag(_part_with_finder(ParallelToAxisRule(axis=StringParameter(value="Z"))))
    assert "ParallelToAxisRule" in dag["serializableNodes"]


def test_on_face_rule_round_trips():
    inner = EdgeFinder(rule=IsCircleRule())
    dag = show_dag(_part_with_finder(OnFaceRule(face_finder=inner)))
    assert "OnFaceRule" in dag["serializableNodes"]


def test_sort_by_rule_round_trips():
    rule = SortByRule(
        rule=LengthRangeRule(min=0.0, max=100.0),
        by=StringParameter(value="LENGTH"),
    )
    dag = show_dag(_part_with_finder(rule))
    assert "SortByRule" in dag["serializableNodes"]
