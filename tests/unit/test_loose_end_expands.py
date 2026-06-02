"""Loose-end @expand follow-ups: SlotCenterPoint, EllipticalCenterArc,
TappedHole.

TangentArc, JernArc and SlotArc need real geometry helpers and ship in a
later commit."""

import math

from cadbuildr.foundation.gen.models import (
    Box,
    EllipseArc,
    EllipticalCenterArc,
    Extrusion,
    Hole,
    Part,
    Point,
    Sketch,
    SlotCenterPoint,
    SlotCenterToCenter,
    TappedHole,
)
from cadbuildr.foundation.dag_utils import show_dag


# ---------- SlotCenterPoint ----------

def test_slot_center_point_expands_to_slot_center_to_center():
    s_part = type("_P", (Part,), {})()
    s = Sketch(s_part.xy())
    slot = SlotCenterPoint(center=Point(s, 0, 0), point=Point(s, 12, 0), height=4)
    inner = slot.expand()
    assert isinstance(inner, SlotCenterToCenter)
    assert (inner.p1.x.value, inner.p1.y.value) == (0, 0)
    assert (inner.p2.x.value, inner.p2.y.value) == (12, 0)
    assert inner.height.value == 4


# ---------- EllipticalCenterArc ----------

def test_elliptical_center_arc_converts_degrees_to_radians():
    s_part = type("_P", (Part,), {})()
    s = Sketch(s_part.xy())
    arc = EllipticalCenterArc(
        center=s.origin,
        x_radius=10.0,
        y_radius=5.0,
        start_angle_deg=0.0,
        end_angle_deg=90.0,
    )
    inner = arc.expand()
    assert isinstance(inner, EllipseArc)
    assert inner.a.value == 10.0
    assert inner.b.value == 5.0
    # 0° → 0 rad; 90° → π/2 rad.
    assert math.isclose(inner.start_angle.value, 0.0, abs_tol=1e-9)
    assert math.isclose(inner.end_angle.value, math.pi / 2, abs_tol=1e-9)


# ---------- TappedHole ----------

def test_tapped_hole_expands_to_hole_with_half_diameter_radius():
    s_part = type("_P", (Part,), {})()
    s = Sketch(s_part.xy())
    hole = TappedHole(point=s.origin, thread_size=5.0, depth=10.0)
    inner = hole.expand()
    assert isinstance(inner, Hole)
    # M5 → radius 2.5
    assert inner.radius.value == 2.5
    assert inner.depth.value == 10.0


def test_tapped_hole_lands_in_dag_via_hole_chain():
    """End-to-end: TappedHole inside a part must FULLY reduce.

    TappedHole expands into a Hole, which itself expands into an
    Extrusion(cut=true). `add_operation` expands transitively, so no raw Hole
    node survives in the DAG. (A leftover Hole node crashed the replicad kernel
    — it routes Hole through the Extrusion handler, whose deps don't match —
    which is what broke the documentation /Foundation/Parts/Primitives/holes
    page.)"""

    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            self.add_operation(Box(s.origin, w=20, h=20, d=10))
            self.add_operation(TappedHole(point=s.origin, thread_size=5.0, depth=10.0))

    dag = show_dag(_Part())
    serializable = dag["serializableNodes"]
    # No bespoke Hole node should remain — it must expand to an Extrusion.
    holes = [n for n in dag["DAG"].values() if n["type"] == serializable.get("Hole")]
    assert len(holes) == 0
    # Box → Extrusion plus TappedHole → Hole → Extrusion = two Extrusions.
    extrusions = [n for n in dag["DAG"].values() if n["type"] == serializable["Extrusion"]]
    assert len(extrusions) == 2
    # The bore radius FloatParameter should be 2.5 (M5 → 5/2).
    fp_type = serializable["FloatParameter"]
    fp_values = [
        n["params"]["value"]
        for n in dag["DAG"].values()
        if n["type"] == fp_type and isinstance(n["params"].get("value"), (int, float))
    ]
    assert 2.5 in fp_values
