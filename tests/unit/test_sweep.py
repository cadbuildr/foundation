"""Tests for Sweep / MultiSectionSweep DAG serialization (regression for issues #638, #652)."""

import pytest
from cadbuildr.foundation import (
    Part, Sketch, Circle, Hexagon, Spline3D, Point3D, Sweep,
    PlaneFactory, MultiSectionSweep,
)
from cadbuildr.foundation.dag_utils import show_dag


def test_sweep_with_circle_profile():
    class SweepSpline(Part):
        def __init__(self):
            s = Sketch(self.xy())
            profile = Circle(s.origin, 3)
            path = Spline3D(
                points=[Point3D(0, 0, 0), Point3D(20, 10, 30), Point3D(40, -5, 60)]
            )
            self.add_operation(Sweep(profile=profile, path=path))

    dag = show_dag(SweepSpline())
    assert "DAG" in dag
    assert len(dag["DAG"]) > 0


def test_sweep_with_hexagon_profile():
    """Regression test: Hexagon profile caused circular reference in show_dag."""
    class SweepTwist(Part):
        def __init__(self):
            s = Sketch(self.xy())
            profile = Hexagon(s.origin, 8)
            path = Spline3D(points=[Point3D(0, 0, 0), Point3D(0, 0, 60)])
            self.add_operation(Sweep(profile=profile, path=path, twist=180.0))

    dag = show_dag(SweepTwist())
    assert "DAG" in dag
    assert len(dag["DAG"]) > 0
    assert "Hexagon" in dag["serializableNodes"]


def test_multi_section_sweep_with_mixed_profiles():
    """Regression test: multi-section sweep with Circle/Hexagon profiles (issue #652).

    Hexagon was missing from the explicit skip-list in foundation_hooks 0.2.7, causing
    a circular-reference error when pydantic_to_dag traversed Hexagon.sketch → Sketch.elements
    → Hexagon (already in processing set). The isinstance(obj, SketchElementMixin) check
    covers all profile types regardless of which explicit names were listed.
    """
    class MultiSectionSweepDemo(Part):
        def __init__(self):
            pf = PlaneFactory()
            p0 = self.xy()
            p1 = pf.get_parallel_plane(p0, 30)
            p2 = pf.get_parallel_plane(p0, 60)
            s0 = Sketch(p0)
            s1 = Sketch(p1)
            s2 = Sketch(p2)
            profiles = [
                Circle(s0.origin, 15),
                Hexagon(s1.origin, 12),
                Circle(s2.origin, 8),
            ]
            spine = Spline3D(
                points=[Point3D(0, 0, 0), Point3D(5, 0, 30), Point3D(0, 0, 60)]
            )
            self.add_operation(MultiSectionSweep(profiles=profiles, path=spine))

    dag = show_dag(MultiSectionSweepDemo())
    assert "DAG" in dag
    assert len(dag["DAG"]) > 0
    assert "Hexagon" in dag["serializableNodes"]
    assert "MultiSectionSweep" in dag["serializableNodes"]
