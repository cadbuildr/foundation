"""Unit tests for CounterBoreHole + CounterSinkHole."""

import pytest

from cadbuildr.foundation.gen.models import (
    Part,
    Sketch,
    CounterBoreHole,
    CounterSinkHole,
    Box,
)
from cadbuildr.foundation.dag_utils import show_dag


def test_counterbore_expands_to_lathe_with_l_profile():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Box(s.origin, w=40, h=40, d=15))
            self.add_operation(
                CounterBoreHole(s.origin, radius=3, depth=12, cbore_radius=6, cbore_depth=4)
            )

    dag = show_dag(_Part())
    serializable = dag["serializableNodes"]
    polygons = [n for n in dag["DAG"].values() if n["type"] == serializable["Polygon"]]
    # The counterbore profile is a 6-line polygon.
    cb_polygon = next(p for p in polygons if len(p["deps"]["lines"]) == 6)
    assert cb_polygon is not None


def test_counterbore_rejects_invalid_geometry():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            # cbore_radius == radius → invalid
            self.add_operation(
                CounterBoreHole(s.origin, radius=5, depth=10, cbore_radius=5, cbore_depth=2)
            )

    with pytest.raises(ValueError, match="cbore_radius"):
        show_dag(_Part())


def test_countersink_expands_to_lathe_with_5_line_profile():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Box(s.origin, w=40, h=40, d=15))
            self.add_operation(
                CounterSinkHole(
                    s.origin,
                    radius=3,
                    depth=12,
                    csink_radius=6,
                    csink_angle_deg=82,
                )
            )

    dag = show_dag(_Part())
    polygons = [n for n in dag["DAG"].values() if n["type"] == dag["serializableNodes"]["Polygon"]]
    cs_polygon = next(p for p in polygons if len(p["deps"]["lines"]) == 5)
    assert cs_polygon is not None
