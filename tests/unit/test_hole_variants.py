"""Unit tests for CounterBoreHole + CounterSinkHole."""

import pytest

from cadbuildr.foundation.gen.models import (
    Part,
    Sketch,
    Point,
    Hole,
    TappedHole,
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


def _node_type_names(dag):
    inv = {v: k for k, v in dag["serializableNodes"].items()}
    return [inv[n["type"]] for n in dag["DAG"].values()]


def test_tapped_hole_expands_transitively_to_extrusion():
    """TappedHole -> Hole -> Extrusion must fully reduce.

    TappedHole expands into a Hole, which itself expands into an Extrusion.
    A single (non-transitive) expansion leaves a raw `Hole` node in the DAG.
    The replicad kernel has no real Hole handler (it routes Hole through the
    Extrusion handler, which then fails on the mismatched deps), so a leftover
    Hole node makes the whole part fail to render — this was the documentation
    /Foundation/Parts/Primitives/holes failure. Guard against the regression.
    """
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Box(s.origin, w=40, h=20, d=10))
            self.add_operation(TappedHole(point=Point(s, 0, 0), thread_size=5, depth=10))

    type_names = _node_type_names(show_dag(_Part()))
    assert "Hole" not in type_names
    assert "Extrusion" in type_names


def test_plate_with_all_four_hole_variants_has_no_raw_hole_node():
    """The full documentation holes_example must serialize to kernel-ready nodes."""
    class _Plate(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Box(s.origin, w=80, h=20, d=10))
            self.add_operation(Hole(Point(s, -30, 0), radius=2, depth=10))
            self.add_operation(
                CounterBoreHole(Point(s, -10, 0), radius=2, depth=10, cbore_radius=4, cbore_depth=3)
            )
            self.add_operation(
                CounterSinkHole(Point(s, 10, 0), radius=2, depth=10, csink_radius=4, csink_angle_deg=82)
            )
            self.add_operation(TappedHole(point=Point(s, 30, 0), thread_size=5, depth=10))

    type_names = _node_type_names(show_dag(_Plate()))
    # No bespoke sugar nodes should survive; only terminal kernel primitives.
    assert "Hole" not in type_names
    assert "TappedHole" not in type_names
    assert "CounterBoreHole" not in type_names
    assert "CounterSinkHole" not in type_names
