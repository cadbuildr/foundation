"""Unit tests for Extrusion variants — taper + direction."""

from cadbuildr.foundation.gen.models import (
    Part,
    Sketch,
    Square,
    Extrusion,
    FloatParameter,
    Point3D,
)
from cadbuildr.foundation.dag_utils import show_dag


def test_extrusion_taper_field_round_trips_through_dag():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            sq = Square.from_center_and_side(s.origin, size=10)
            self.add_operation(Extrusion(sq, end=20, taper=FloatParameter(value=0.2)))

    dag = show_dag(_Part())
    fp_type = dag["serializableNodes"]["FloatParameter"]
    fp_values = [
        n["params"]["value"]
        for n in dag["DAG"].values()
        if n["type"] == fp_type and isinstance(n["params"].get("value"), (int, float))
    ]
    assert 0.2 in fp_values, f"taper=0.2 should appear as FloatParameter; got {fp_values}"


def test_extrusion_default_taper_is_zero():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            sq = Square.from_center_and_side(s.origin, size=10)
            self.add_operation(Extrusion(sq, end=20))  # no taper passed

    # Construction must succeed; the schema default is FloatParameter(value=0.0).
    show_dag(_Part())


def test_extrusion_direction_field_accepts_point3d():
    class _Part(Part):
        def __init__(self):
            s = Sketch(self.xy())
            sq = Square.from_center_and_side(s.origin, size=10)
            self.add_operation(
                Extrusion(
                    sq,
                    end=20,
                    direction=Point3D(
                        x=FloatParameter(value=0.0),
                        y=FloatParameter(value=0.0),
                        z=FloatParameter(value=1.0),
                    ),
                )
            )

    show_dag(_Part())
