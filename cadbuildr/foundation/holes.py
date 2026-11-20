"""ISO metric screw data for the hole wizard (TappedHole, ClearanceHole).

Coarse-pitch tap drills follow the usual "nominal − pitch" shop rule (ISO 2306
recommended sizes); clearance diameters are ISO 273 close / normal (medium) /
loose (coarse) series.
"""

from __future__ import annotations

from typing import Any

# size: (coarse pitch, tap drill Ø, clearance Ø close, normal, loose)
ISO_METRIC_COARSE: dict[float, tuple[float, float, float, float, float]] = {
    1.6: (0.35, 1.25, 1.7, 1.8, 2.0),
    2.0: (0.40, 1.6, 2.2, 2.4, 2.6),
    2.5: (0.45, 2.05, 2.7, 2.9, 3.1),
    3.0: (0.50, 2.5, 3.2, 3.4, 3.6),
    4.0: (0.70, 3.3, 4.3, 4.5, 4.8),
    5.0: (0.80, 4.2, 5.3, 5.5, 5.8),
    6.0: (1.00, 5.0, 6.4, 6.6, 7.0),
    8.0: (1.25, 6.8, 8.4, 9.0, 10.0),
    10.0: (1.50, 8.5, 10.5, 11.0, 12.0),
    12.0: (1.75, 10.2, 13.0, 13.5, 14.5),
    14.0: (2.00, 12.0, 15.0, 15.5, 16.5),
    16.0: (2.00, 14.0, 17.0, 17.5, 18.5),
    20.0: (2.50, 17.5, 21.0, 22.0, 24.0),
    24.0: (3.00, 21.0, 25.0, 26.0, 28.0),
    30.0: (3.50, 26.5, 31.0, 33.0, 35.0),
}

_FIT_COLUMN = {"CLOSE": 2, "NORMAL": 3, "LOOSE": 4}


def _row(size: float) -> tuple[float, float, float, float, float]:
    for key, row in ISO_METRIC_COARSE.items():
        if abs(key - size) < 1e-6:
            return row
    sizes = ", ".join(f"M{k:g}" for k in ISO_METRIC_COARSE)
    raise ValueError(
        f"M{size:g} is not in the ISO metric coarse table ({sizes}). "
        "Use Hole(point, radius, depth) with an explicit radius instead."
    )


def tap_drill_diameter(size: float) -> float:
    """Tap drill Ø for an ISO metric coarse thread (M6 → 5.0)."""
    return _row(size)[1]


def clearance_diameter(size: float, fit: str = "NORMAL") -> float:
    """ISO 273 clearance hole Ø for screw size `size` (M6 normal → 6.6)."""
    key = str(getattr(fit, "value", fit)).upper()
    if key not in _FIT_COLUMN:
        raise ValueError(f"Unknown hole fit {fit!r}; use CLOSE, NORMAL or LOOSE")
    return _row(size)[_FIT_COLUMN[key]]


def hole_point_from_anchor(anchor: Any) -> Any:
    """Sketch point for a hole drilled at ``anchor``.

    Anchors point +Z *out* of a face; holes extrude along their sketch normal.
    The point therefore lives on a plane flipped 180° about the anchor's X
    axis (normal = anchor -Z, X = anchor X), so every hole wizard (Hole,
    TappedHole, ClearanceHole, CounterBoreHole, CounterSinkHole) drills into
    the face, entering at the anchor origin. The plane's frame is a child of
    the anchor frame, so the hole follows the part however it is placed.
    """
    from .gen.models import (
        BoolParameter,
        Frame,
        Plane,
        Sketch,
        StringParameter,
    )

    name = anchor.name.value
    plane = Plane(
        frame=Frame(
            top_frame=anchor.frame,
            name=StringParameter(value=f"hole_{name}_frame"),
            display=BoolParameter(value=False),
            position=[0.0, 0.0, 0.0],
            quaternion=[0.0, 1.0, 0.0, 0.0],
        ),
        name=StringParameter(value=f"hole_{name}"),
        display=BoolParameter(value=False),
    )
    return Sketch(plane).origin
