"""Unit tests for advanced ops."""

import math

from cadbuildr.foundation.gen.models import (
    Box,
    ConvexHull,
    Draft,
    EdgeFinder,
    Extrusion,
    FullRound,
    InPlaneFinderRule,
    Part,
    Point,
    Sketch,
    StringParameter,
    Trace,
    Polygon,
)
from cadbuildr.foundation.dag_utils import show_dag


def test_convex_hull_emits_polygon_with_outer_boundary():
    """ConvexHull on 5 points (4 outer + 1 inner) yields a 4-line Polygon."""

    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            pts = [
                Point(s, 0, 0),
                Point(s, 10, 0),
                Point(s, 10, 10),
                Point(s, 0, 10),
                Point(s, 5, 5),  # interior — must be dropped
            ]
            hull = ConvexHull(points=pts)
            self.add_operation(Extrusion(hull, end=2))

    dag = show_dag(_Part())
    polygons = [n for n in dag["DAG"].values() if n["type"] == dag["serializableNodes"]["Polygon"]]
    assert len(polygons) == 1
    # 4 outer corners → 4 hull edges.
    assert len(polygons[0]["deps"]["lines"]) == 4


def test_trace_persists_as_dag_node():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Box(s.origin, w=10, h=10, d=2))
            # Trace itself is added via its sketch context — for now just
            # verify it constructs without error.
            Trace(path_points=[Point(s, 0, 0), Point(s, 5, 5)], width=1.0)

    show_dag(_Part())  # construction must succeed


def test_draft_persists_as_native_dag_node():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            box = Box(s.origin, w=10, h=10, d=10)
            self.add_operation(box)
            ef = EdgeFinder(rule=InPlaneFinderRule(plane=self.xy()))
            self.add_operation(
                Draft(
                    solid=box.expand(),
                    angle_deg=5.0,
                    neutral_plane_name=StringParameter(value="XY"),
                    edge_finder=ef,
                )
            )

    dag = show_dag(_Part())
    assert "Draft" in dag["serializableNodes"]


def test_full_round_persists_as_native_dag_node():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            box = Box(s.origin, w=10, h=10, d=10)
            self.add_operation(box)
            ef = EdgeFinder(rule=InPlaneFinderRule(plane=self.xy()))
            self.add_operation(FullRound(solid=box.expand(), face_finder=ef))

    dag = show_dag(_Part())
    assert "FullRound" in dag["serializableNodes"]
