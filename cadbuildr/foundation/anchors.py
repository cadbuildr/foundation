"""Construction-time anchor helpers: patterns and degree-named rotations.

Hand-written (no schema nodes): every helper returns ordinary ``Anchor``
nodes whose frames are children of the base anchor's frame, so the DAG only
ever sees plain anchors and frames.

Patterns::

    holes = part.anchor("corner").linear_pattern(4, 25.0, direction=(1, 0, 0))
    bolts = part.anchor("hub").polar_pattern(6, radius=40.0)
    beads = part.anchor("start").along_path([(0, 0, 0), (100, 0, 0), (100, 50, 0)], 8)
    part.add_anchors(bolts)          # optional: register them for lookup

Naming: pattern element ``i`` is ``<base>_<i>`` (``<base>_<name>_<i>`` with
``name=``), 0-based like the returned list. Names are unique per owner; see
the naming rule in ``compute_functions`` (derived names dedupe, registered
names raise).

Angles: radians everywhere in the 3D API; ``*_deg`` names/keywords take
degrees (``Part.rotate_deg``, ``Anchor.rotated_deg``, ``angle_deg=``).
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Optional, Sequence

import numpy as np

from .compute_functions import (
    make_child_anchor,
    unique_derived_anchor_stem,
)
from .gen.models import Anchor, Assembly, Part
from .math_utils import (
    axes_from_x_and_up,
    axis_angle_to_quaternion,
    quaternion_from_axes,
    unit_vector,
)

_IDENTITY_Q = [1.0, 0.0, 0.0, 0.0]


def _check_count(n: int, label: str) -> int:
    if isinstance(n, bool) or int(n) != n or n < 1:
        raise ValueError(f"{label}: n must be a positive integer, got {n!r}")
    return int(n)


def _pattern(
    base: Any, name: Optional[str], placements: list[tuple[list[float], list[float]]]
) -> list[Any]:
    stem = f"{base.name.value}_{name}" if name else base.name.value
    stem = unique_derived_anchor_stem(base, stem, len(placements))
    return [
        make_child_anchor(base, f"{stem}_{i}", position, quaternion)
        for i, (position, quaternion) in enumerate(placements)
    ]


def _resolve_angle(
    angle: Optional[float], angle_deg: Optional[float], default: float, label: str
) -> float:
    if angle is not None and angle_deg is not None:
        raise ValueError(f"{label}: pass either the radian or the _deg form, not both")
    if angle_deg is not None:
        return math.radians(float(angle_deg))
    return default if angle is None else float(angle)


# --------------------------------------------------------------------------- #
# Patterns
# --------------------------------------------------------------------------- #


def anchor_linear_pattern(
    self: Any,
    n: int,
    pitch: float,
    direction: Sequence[float] = (1.0, 0.0, 0.0),
    *,
    name: Optional[str] = None,
) -> list[Any]:
    """``n`` anchors spaced ``pitch`` apart along ``direction``.

    ``direction`` is in this anchor's local frame (like ``offset``); element
    0 sits on this anchor. All elements keep this anchor's orientation.
    Names: ``<base>_0 .. <base>_<n-1>`` (``<base>_<name>_<i>`` with ``name``).
    """
    n = _check_count(n, "linear_pattern")
    step = unit_vector(direction, "direction") * float(pitch)
    return _pattern(
        self, name, [((step * i).tolist(), list(_IDENTITY_Q)) for i in range(n)]
    )


def anchor_polar_pattern(
    self: Any,
    n: int,
    radius: Optional[float] = None,
    angle: Optional[float] = None,
    *,
    angle_deg: Optional[float] = None,
    start_angle: Optional[float] = None,
    start_angle_deg: Optional[float] = None,
    name: Optional[str] = None,
) -> list[Any]:
    """``n`` anchors rotated about this anchor's Z axis.

    Element ``i`` is rotated by ``start_angle + i * step`` about local Z, so
    its X points radially outward and its Z stays parallel to this anchor's
    Z. With ``radius`` it also sits at that distance along its own X (a bolt
    circle); with ``radius=None`` all elements share this anchor's origin
    (a clocking pattern).

    ``angle`` (radians, default a full turn) is the angular span. Like
    ``PolarLocations``: a full turn spaces ``angle / n`` (no duplicate at
    360°); a partial span spaces ``angle / (n - 1)`` so both ends are hit.
    ``angle_deg`` / ``start_angle_deg`` are the degree forms.
    """
    n = _check_count(n, "polar_pattern")
    span = _resolve_angle(angle, angle_deg, 2.0 * math.pi, "polar_pattern angle")
    start = _resolve_angle(
        start_angle, start_angle_deg, 0.0, "polar_pattern start_angle"
    )
    if math.isclose(abs(span), 2.0 * math.pi):
        step = span / n
    else:
        step = span / max(n - 1, 1)
    r = 0.0 if radius is None else float(radius)
    placements = []
    for i in range(n):
        theta = start + i * step
        position = [r * math.cos(theta), r * math.sin(theta), 0.0]
        placements.append((position, axis_angle_to_quaternion([0.0, 0.0, 1.0], theta)))
    return _pattern(self, name, placements)


def _as_points(path: Any) -> np.ndarray:
    if hasattr(path, "tolist") and not isinstance(path, (list, tuple)):
        path = path.tolist()
    points = []
    for p in path:
        if hasattr(p, "to_array"):
            p = p.to_array()
        coords = [float(c) for c in p]
        if len(coords) == 2:
            coords.append(0.0)
        if len(coords) != 3:
            raise ValueError(f"along_path: points must be 2D or 3D, got {coords}")
        points.append(coords)
    arr = np.asarray(points, dtype=float).reshape(-1, 3)
    # Drop consecutive duplicates: they have no tangent.
    keep = [0] + [
        i for i in range(1, len(arr)) if np.linalg.norm(arr[i] - arr[i - 1]) > 1e-12
    ]
    arr = arr[keep]
    if len(arr) < 2:
        raise ValueError("along_path: path needs at least two distinct points")
    return arr


def anchor_along_path(
    self: Any,
    path: Iterable[Sequence[float]],
    n: int,
    *,
    up: Sequence[float] = (0.0, 0.0, 1.0),
    name: Optional[str] = None,
) -> list[Any]:
    """``n`` anchors evenly spaced (by arc length) along a polyline.

    ``path`` is a sequence of 2D/3D points (or ``Point3D``) in this anchor's
    local frame. Each element's X is the path tangent (the outgoing segment
    at a vertex, the last segment at the end); its Z is ``up`` (default this
    anchor's Z) with the tangent component removed. Where the tangent is
    parallel to ``up``, Z falls back to local +X, then +Y.

    Spacing: an open path puts the first and last elements on its ends
    (``length / (n - 1)``); a closed path (last point == first) spaces
    ``length / n`` with no duplicate at the seam. ``n=1`` gives the start.
    """
    n = _check_count(n, "along_path")
    pts = _as_points(path)
    seg = np.diff(pts, axis=0)
    seg_len = np.linalg.norm(seg, axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg_len)])
    total = float(cum[-1])
    closed = len(pts) > 2 and np.linalg.norm(pts[-1] - pts[0]) <= 1e-9 * max(total, 1.0)
    spacing = total / n if closed else (total / (n - 1) if n > 1 else 0.0)

    placements = []
    for i in range(n):
        s = min(i * spacing, total)
        k = int(np.searchsorted(cum, s, side="right")) - 1
        k = min(max(k, 0), len(seg) - 1)
        tangent = seg[k] / seg_len[k]
        point = pts[k] + tangent * (s - cum[k])
        axes = None
        for hint in (up, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)):
            try:
                axes = axes_from_x_and_up(tangent, hint)
                break
            except ValueError:
                continue
        assert axes is not None  # one of three orthogonal hints always works
        placements.append((point.tolist(), quaternion_from_axes(*axes)))
    return _pattern(self, name, placements)


# --------------------------------------------------------------------------- #
# Degree-named rotations (radians stay the default everywhere).
# --------------------------------------------------------------------------- #


def anchor_rotated_deg(
    self: Any,
    angle_deg: float,
    axis: Sequence[float] = (0.0, 0.0, 1.0),
    name: str = "rotated",
) -> Any:
    """``Anchor.rotated`` with the angle in degrees."""
    return self.rotated(math.radians(angle_deg), axis=list(axis), name=name)


def component_rotate_deg(
    self: Any, angle_deg: float, axis: Sequence[float] = (0.0, 0.0, 1.0)
) -> bool:
    """``Part/Assembly.rotate`` with the angle in degrees (same arg order)."""
    return self.rotate(math.radians(angle_deg), list(axis))


def component_add_anchors(self: Any, anchors: Iterable[Any]) -> list[Any]:
    """``add_anchor`` for each anchor (e.g. a pattern); returns them as a list."""
    return [self.add_anchor(anchor) for anchor in anchors]


setattr(Anchor, "linear_pattern", anchor_linear_pattern)
setattr(Anchor, "polar_pattern", anchor_polar_pattern)
setattr(Anchor, "along_path", anchor_along_path)
setattr(Anchor, "rotated_deg", anchor_rotated_deg)
for _cls in (Part, Assembly):
    setattr(_cls, "rotate_deg", component_rotate_deg)
    setattr(_cls, "add_anchors", component_add_anchors)

__all__ = [
    "anchor_linear_pattern",
    "anchor_polar_pattern",
    "anchor_along_path",
    "anchor_rotated_deg",
    "component_rotate_deg",
    "component_add_anchors",
]
