"""Tests for Sweep DAG serialization (regression for issue #638)."""

import pytest
from cadbuildr.foundation import (
    Part, Sketch, Circle, Hexagon, Spline3D, Point3D, Sweep
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
