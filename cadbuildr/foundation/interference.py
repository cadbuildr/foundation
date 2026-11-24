"""Interference (clash) check between the parts of an assembly.

Foundation has no geometry kernel, so the check works on bounding volumes
computed from data Python already holds:

* **per-part extents**, estimated from the part's operations (2D sketch shape
  bounds + extrusion lengths, revolve radii, ...) as a list of oriented boxes
  in the part frame — see :func:`estimate_part_extents` for what is covered;
* **placed transforms**, read from the live component frames (``add_component``
  poses, joint placements, nested sub-assemblies).

Each pair of parts is tested with a separating-axis test on oriented bounding
boxes (OBB), so rotated parts are handled exactly at the box level. Boxes are
outer bounds of the solids: a reported overlap means the *bounding volumes*
interpenetrate by ``depth`` mm (cut features and concave outlines are not
subtracted). A part whose extents cannot be bounded honestly (a sweep, text,
sheet metal, ...) is reported as ``"unknown"`` against every other part instead
of being guessed; supply its box with :func:`set_part_extents` or the
``extents=`` argument.

Contacts that are part of the design are never reported:

* parts connected by a joint (``add_joint``, ``ground`` excluded) or by an
  ``add_connection`` joint, including loop-closing ones;
* parts touched by the same Connection's modifiers (a tenon in its mortise, a
  screw in the hole the connection drilled);
* pairs listed in ``allow=``.

**Exact mode** (``exact=True``) compares the real solids instead: every part
is meshed (by default through the kernel API, :func:`kernel_api_mesher`; pass
``mesher=`` to supply meshes yourself), placed with the same transforms, and
each pair's intersection volume is computed with ``manifold3d``
(``pip install 'cadbuildr-foundation[exact]'``). A pair is reported when the
solids share more than ``volume_tol`` mm³. Jointed / connected pairs are
checked too — a joint says the parts are *meant* to touch, not that they may
interpenetrate (two meshed gears, a pin in its hole); exempt a pair explicitly
with ``allow=``.

Entry point: ``assembly.check_interference(tolerance=0.0, allow=[...])``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional, Sequence, Union

import numpy as np

from .math_utils import quaternion_to_axes, tf_relative_to_frame

__all__ = [
    "OBB",
    "PartExtents",
    "Interference",
    "InterferenceError",
    "obb_penetration",
    "obb_intersects",
    "obb_overlap_volume",
    "estimate_part_extents",
    "set_part_extents",
    "check_interference",
    "kernel_api_mesher",
    "solid_overlap",
    "FINE_MESH_CONFIG",
    "DEFAULT_DEPTH_TOL",
]

_EXPLICIT_EXTENTS_ATTR = "_explicit_extents"
_EPS = 1e-9


# --------------------------------------------------------------------------- #
# Oriented bounding boxes
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, eq=False)
class OBB:
    """Oriented box: ``center`` (3,), unit ``axes`` (3, 3) as columns, ``half``
    extents (3,) along those axes."""

    center: np.ndarray
    axes: np.ndarray
    half: np.ndarray

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "center", np.asarray(self.center, dtype=float).reshape(3)
        )
        object.__setattr__(
            self, "axes", np.asarray(self.axes, dtype=float).reshape(3, 3)
        )
        object.__setattr__(
            self, "half", np.maximum(np.asarray(self.half, dtype=float).reshape(3), 0.0)
        )

    @classmethod
    def from_bounds(cls, lo: Sequence[float], hi: Sequence[float]) -> "OBB":
        """Axis-aligned box between corners ``lo`` and ``hi``."""
        lo_a, hi_a = np.asarray(lo, dtype=float), np.asarray(hi, dtype=float)
        return cls((lo_a + hi_a) / 2.0, np.eye(3), np.abs(hi_a - lo_a) / 2.0)

    @classmethod
    def from_points(
        cls, points: Iterable[Sequence[float]], axes: Optional[np.ndarray] = None
    ) -> "OBB":
        """Tightest box with the given ``axes`` (default: identity) enclosing
        ``points``."""
        pts = np.asarray(list(points), dtype=float).reshape(-1, 3)
        ax = np.eye(3) if axes is None else np.asarray(axes, dtype=float)
        local = pts @ ax
        lo, hi = local.min(axis=0), local.max(axis=0)
        return cls(ax @ ((lo + hi) / 2.0), ax, (hi - lo) / 2.0)

    def corners(self) -> np.ndarray:
        """The 8 corners, shape (8, 3)."""
        signs = np.array(
            [[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)],
            dtype=float,
        )
        return self.center + (signs * self.half) @ self.axes.T

    def transformed(self, rotation: np.ndarray, translation: Sequence[float]) -> "OBB":
        """This box moved by ``x -> R x + t``."""
        r = np.asarray(rotation, dtype=float)
        return OBB(
            r @ self.center + np.asarray(translation, dtype=float),
            r @ self.axes,
            self.half,
        )

    def inflated(self, amount: float) -> "OBB":
        return OBB(self.center, self.axes, self.half + amount)

    @property
    def volume(self) -> float:
        return float(np.prod(2.0 * self.half))


def _sat_axes(a: OBB, b: OBB) -> list[np.ndarray]:
    axes = [a.axes[:, i] for i in range(3)] + [b.axes[:, j] for j in range(3)]
    for i in range(3):
        for j in range(3):
            c = np.cross(a.axes[:, i], b.axes[:, j])
            n = float(np.linalg.norm(c))
            if n > 1e-9:
                axes.append(c / n)
    return axes


def obb_penetration(a: OBB, b: OBB) -> float:
    """Signed separating-axis overlap of two boxes.

    Positive: the boxes interpenetrate and this is the smallest translation
    (mm) that separates them. Zero: faces touch. Negative: a separating axis
    exists and the boxes are at least ``-value`` apart along it.
    """
    d = b.center - a.center
    best = math.inf
    for axis in _sat_axes(a, b):
        ra = float(a.half @ np.abs(a.axes.T @ axis))
        rb = float(b.half @ np.abs(b.axes.T @ axis))
        overlap = ra + rb - abs(float(d @ axis))
        if overlap < best:
            best = overlap
    return best


def obb_intersects(a: OBB, b: OBB, margin: float = 0.0) -> bool:
    """Closed-box separating-axis test (touching counts as intersecting).

    ``margin`` shrinks both boxes' half-extents first, so surface contact and
    fit clearances up to ``margin`` per side do not count (woodworking's
    occupancy check uses this form).
    """
    if margin:
        a = OBB(a.center, a.axes, np.maximum(a.half - margin, 0.0))
        b = OBB(b.center, b.axes, np.maximum(b.half - margin, 0.0))
    return obb_penetration(a, b) >= -1e-12


def _aligned_permutation(a: OBB, b: OBB) -> Optional[np.ndarray]:
    """|R| as a permutation matrix when b's axes are a's up to order/sign."""
    r = np.abs(a.axes.T @ b.axes)
    p = np.round(r)
    if (
        np.allclose(r, p, atol=1e-9)
        and np.allclose(p.sum(axis=0), 1)
        and np.allclose(p.sum(axis=1), 1)
    ):
        return p
    return None


def obb_overlap_volume(a: OBB, b: OBB, samples: int = 16) -> float:
    """Volume (mm³) of the intersection of two boxes.

    Exact when the boxes' axes coincide up to order and sign; otherwise a
    deterministic ``samples³`` grid estimate over the smaller box.
    """
    if obb_penetration(a, b) <= 0.0:
        return 0.0
    perm = _aligned_permutation(a, b)
    if perm is not None:
        hb = perm @ b.half  # b's half extents along a's axes
        cb = a.axes.T @ (b.center - a.center)
        lo = np.maximum(-a.half, cb - hb)
        hi = np.minimum(a.half, cb + hb)
        return float(np.prod(np.maximum(hi - lo, 0.0)))
    small, big = (a, b) if a.volume <= b.volume else (b, a)
    ticks = (np.arange(samples) + 0.5) / samples * 2.0 - 1.0
    grid = np.stack(np.meshgrid(ticks, ticks, ticks, indexing="ij"), axis=-1).reshape(
        -1, 3
    )
    pts = small.center + (grid * small.half) @ small.axes.T
    local = (pts - big.center) @ big.axes
    inside = np.all(np.abs(local) <= big.half + _EPS, axis=1)
    return float(inside.mean() * small.volume)


# --------------------------------------------------------------------------- #
# Part extents
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PartExtents:
    """Bounding volume of one part, in the part frame.

    ``boxes`` is the union of oriented boxes bounding the part's solid.
    ``unknown`` lists why the part could not be bounded; when it is non-empty
    the boxes are not trustworthy and the part is reported as unknown.
    ``source`` is ``"estimated"`` or ``"explicit"``.
    """

    boxes: tuple[OBB, ...] = ()
    unknown: tuple[str, ...] = ()
    source: str = "estimated"

    @property
    def known(self) -> bool:
        return not self.unknown


class _Unknown(Exception):
    """An operation's extent cannot be bounded from Python-side data."""


def _val(x: Any) -> float:
    if x is None:
        raise _Unknown("missing value")
    value = getattr(x, "value", x)
    if value is None:
        raise _Unknown("unresolved parameter")
    if hasattr(value, "value"):  # enum
        value = value.value
    return float(value)


def _expand(node: Any) -> Any:
    from .gen.runtime import Expandable

    for _ in range(100):
        if not isinstance(node, Expandable):
            return node
        node = node.expand()
    raise _Unknown(f"{type(node).__name__} does not expand")


def _xy(point: Any) -> tuple[float, float]:
    return _val(point.x), _val(point.y)


def _arc_bounds(
    p1: Sequence[float], p2: Sequence[float], p3: Sequence[float]
) -> list[tuple[float, float]]:
    """Points bounding the 3-point arc p1 -> (through p3) -> p2."""
    (x1, y1), (x2, y2), (x3, y3) = p1, p2, p3
    d = 2.0 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    pts = [tuple(p1), tuple(p2), tuple(p3)]
    if abs(d) < 1e-12:  # collinear: a straight segment
        return pts
    s1, s2, s3 = x1 * x1 + y1 * y1, x2 * x2 + y2 * y2, x3 * x3 + y3 * y3
    cx = (s1 * (y2 - y3) + s2 * (y3 - y1) + s3 * (y1 - y2)) / d
    cy = (s1 * (x3 - x2) + s2 * (x1 - x3) + s3 * (x2 - x1)) / d
    r = math.hypot(x1 - cx, y1 - cy)
    a1 = math.atan2(y1 - cy, x1 - cx)
    a2 = math.atan2(y2 - cy, x2 - cx)
    a3 = math.atan2(y3 - cy, x3 - cx)

    def ccw(start: float, end: float) -> float:
        return (end - start) % (2.0 * math.pi)

    # Sweep from a1 to a2 in the direction that passes through a3.
    if ccw(a1, a3) <= ccw(a1, a2):
        start, span = a1, ccw(a1, a2)
    else:
        start, span = a2, ccw(a2, a1)
    for k in range(4):
        ang = k * math.pi / 2.0
        if ccw(start, ang) <= span:
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts


def _shape_points_2d(shape: Any) -> list[tuple[float, float]]:
    """Points whose 2D bounding box bounds ``shape`` (sketch coordinates)."""
    shape = _expand(shape)
    name = type(shape).__name__
    if name == "Point":
        return [_xy(shape)]
    if name == "Circle":
        cx, cy = _xy(shape.center)
        r = abs(_val(shape.radius))
        return [(cx - r, cy - r), (cx + r, cy + r)]
    if name in ("Ellipse", "EllipseArc"):
        cx, cy = _xy(shape.center)
        a, b = abs(_val(shape.a)), abs(_val(shape.b))
        return [(cx - a, cy - b), (cx + a, cy + b)]
    if name == "Line":
        return [_xy(shape.p1), _xy(shape.p2)]
    if name == "Arc":
        return _arc_bounds(_xy(shape.p1), _xy(shape.p2), _xy(shape.p3))
    if name in ("Bezier", "BSpline"):  # convex-hull property of control points
        return [_xy(p) for p in shape.points]
    if name == "Polygon":
        return [p for line in shape.lines for p in _shape_points_2d(line)]
    if name in ("CustomClosedShape", "CustomOpenShape"):
        return [p for prim in shape.primitives for p in _shape_points_2d(prim)]
    if name == "Offset2D":
        pts = _shape_points_2d(shape.shape)
        d = abs(_val(shape.distance))
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return [(min(xs) - d, min(ys) - d), (max(xs) + d, max(ys) + d)]
    if name == "Trace":
        w = abs(_val(shape.width)) / 2.0
        pts = [_xy(p) for p in shape.path_points]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return [(min(xs) - w, min(ys) - w), (max(xs) + w, max(ys) + w)]
    # Spline interpolates (may overshoot its points); Text / SVG need a font or
    # an SVG parser: none of these can be bounded without guessing.
    raise _Unknown(f"2D shape {name}")


def _bounds_2d(shapes: Sequence[Any]) -> tuple[float, float, float, float]:
    pts = [p for s in shapes for p in _shape_points_2d(s)]
    if not pts:
        raise _Unknown("empty sketch")
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _rotation(q: Sequence[float]) -> np.ndarray:
    qa = np.asarray(q, dtype=float)
    x, y, z = quaternion_to_axes(list(qa / np.linalg.norm(qa)))
    return np.column_stack([x, y, z]).astype(float)


def _frame_in_part(frame: Any, part_frame: Any) -> tuple[np.ndarray, np.ndarray]:
    """(R, t) of ``frame`` in ``part_frame`` coordinates."""
    try:
        t, q = tf_relative_to_frame(frame, part_frame)
        return _rotation(q), np.asarray(t, dtype=float)
    except ValueError:
        # Not under the part frame (e.g. a plane on a foreign frame): go
        # through the common root.
        t_f, q_f = tf_relative_to_frame(frame, None)
        t_p, q_p = tf_relative_to_frame(part_frame, None)
        r_f, r_p = _rotation(q_f), _rotation(q_p)
        return r_p.T @ r_f, r_p.T @ (np.asarray(t_f) - np.asarray(t_p))


def _sketch_frame(sketch: Any, part_frame: Any) -> tuple[np.ndarray, np.ndarray]:
    if sketch is None:
        raise _Unknown("no sketch")
    return _frame_in_part(sketch.plane.frame, part_frame)


def _vec3(p: Any) -> np.ndarray:
    return np.array([_val(p.x), _val(p.y), _val(p.z)], dtype=float)


def _is_cut(op: Any) -> bool:
    cut = getattr(op, "cut", None)
    return bool(getattr(cut, "value", cut)) if cut is not None else False


def _rot_about(axis: np.ndarray, angle_rad: float) -> np.ndarray:
    axis = axis / np.linalg.norm(axis)
    k = np.array(
        [[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]]
    )
    return np.eye(3) + math.sin(angle_rad) * k + (1 - math.cos(angle_rad)) * (k @ k)


def _extrusion_boxes(op: Any, part_frame: Any) -> list[OBB]:
    r, t = _sketch_frame(op.sketch, part_frame)
    x0, y0, x1, y1 = _bounds_2d(op.shape)
    start, end = _val(op.start), _val(op.end)
    cond = getattr(getattr(op, "end_condition", None), "value", "BLIND") or "BLIND"
    if cond == "SYMMETRIC":
        start, end = -end / 2.0, end / 2.0
    elif cond != "BLIND":
        raise _Unknown(f"Extrusion end_condition {cond} (depth depends on the solid)")
    taper = _val(op.taper) if getattr(op, "taper", None) is not None else 0.0
    if taper < 0:
        # Profile scales by (1 - taper) about a point inside its 2D bounds.
        grow = -taper * max(x1 - x0, y1 - y0)
        x0, y0, x1, y1 = x0 - grow, y0 - grow, x1 + grow, y1 + grow
    base = [np.array([x, y, start]) for x in (x0, x1) for y in (y0, y1)]
    direction = getattr(op, "direction", None)
    if direction is not None and np.linalg.norm(_vec3(direction)) > 1e-9:
        # Skewed prism along a part-frame direction (magnitude ignored).
        d = _vec3(direction)
        d = d / np.linalg.norm(d)
        base_part = [r @ p + t for p in base]
        pts = base_part + [p + (end - start) * d for p in base_part]
        return [OBB.from_points(pts, r)]
    pts = base + [np.array([p[0], p[1], end]) for p in base]
    return [OBB.from_points([r @ p + t for p in pts], r)]


def _lathe_boxes(op: Any, part_frame: Any) -> list[OBB]:
    r, t = _sketch_frame(op.sketch, part_frame)
    x0, y0, x1, y1 = _bounds_2d([op.shape])
    line = op.axis.line
    a = np.array(_xy(line.p1))
    b = np.array(_xy(line.p2))
    u = b - a
    if np.linalg.norm(u) < 1e-12:
        raise _Unknown("Lathe with a zero-length axis")
    u = u / np.linalg.norm(u)
    v = np.array([-u[1], u[0]])
    corners = [np.array([x, y]) for x in (x0, x1) for y in (y0, y1)]
    s = [float((c - a) @ u) for c in corners]
    radius = max(abs(float((c - a) @ v)) for c in corners)
    axes_plane = np.column_stack(
        [[u[0], u[1], 0.0], [v[0], v[1], 0.0], [0.0, 0.0, 1.0]]
    )
    center_plane = (
        np.array([a[0], a[1], 0.0]) + axes_plane[:, 0] * (min(s) + max(s)) / 2.0
    )
    half = [(max(s) - min(s)) / 2.0, radius, radius]
    return [OBB(r @ center_plane + t, r @ axes_plane, half)]


def _sphere_boxes(op: Any, part_frame: Any) -> list[OBB]:
    r, t = _sketch_frame(op.sketch, part_frame)
    cx, cy = _xy(op.center)
    rad = abs(_val(op.radius))
    return [OBB(r @ np.array([cx, cy, 0.0]) + t, r, [rad, rad, rad])]


def _wedge_boxes(op: Any, part_frame: Any) -> list[OBB]:
    # Bottom dx × dy centred on `center`, top ltx ≤ dx, height dz on the
    # sketch normal: bounded by the dx × dy × dz box.
    r, t = _sketch_frame(op.center.sketch, part_frame)
    cx, cy = _xy(op.center)
    dx, dy, dz = abs(_val(op.dx)), abs(_val(op.dy)), _val(op.dz)
    return [
        OBB(
            r @ np.array([cx, cy, dz / 2.0]) + t, r, [dx / 2.0, dy / 2.0, abs(dz) / 2.0]
        )
    ]


def _loft_boxes(op: Any, part_frame: Any) -> list[OBB]:
    if op.guides:
        raise _Unknown("Loft with guide rails")
    if len(op.shapes) > 2 and not getattr(op.ruled, "value", False):
        raise _Unknown("smooth Loft through more than two sections")
    pts = []
    for shape in op.shapes:
        r, t = _sketch_frame(_expand(shape).sketch, part_frame)
        x0, y0, x1, y1 = _bounds_2d([shape])
        pts += [r @ np.array([x, y, 0.0]) + t for x in (x0, x1) for y in (y0, y1)]
    return [OBB.from_points(pts)]


def _solid_boxes(op: Any, part_frame: Any) -> Optional[list[OBB]]:
    """Boxes bounding one operation's contribution, ``None`` if it adds none.

    Raises :class:`_Unknown` when the contribution cannot be bounded.
    """
    op = _expand(op)
    name = type(op).__name__
    if name in (
        "Extrusion",
        "Lathe",
        "Loft",
        "Sphere",
        "Sweep",
        "MultiSectionSweep",
        "ImportStep",
    ) and _is_cut(op):
        return None  # subtractive: never grows the part
    if name == "Extrusion":
        return _extrusion_boxes(op, part_frame)
    if name == "Lathe":
        return _lathe_boxes(op, part_frame)
    if name == "Sphere":
        return _sphere_boxes(op, part_frame)
    if name == "Wedge":
        return _wedge_boxes(op, part_frame)
    if name == "ImportStep":
        # Only the kernel reads STEP geometry; set extents by hand if needed.
        raise _Unknown(f"ImportStep {op.filename.value!r} (use set_extents)")
    if name == "Loft":
        return _loft_boxes(op, part_frame)
    if name in ("Fillet", "Chamfer", "FullRound", "Split"):
        return None  # only removes material / rounds within the hull
    if name in ("DeleteBodies", "KeepBodies"):
        return None  # only removes bodies (the outer bound is kept)
    if name == "BooleanOperation":
        target = _solid_boxes(op.target, part_frame) or []
        kind = getattr(op.op, "value", op.op)
        if kind != "UNION":
            return target  # SUBTRACT / INTERSECT stay within the target
        out = list(target)
        for tool in op.tools:
            out += _solid_boxes(tool, part_frame) or []
        return out
    if name in ("LinearPattern", "PolarPattern", "CurvePattern") and op.shape is None:
        raise _Unknown(f"{name} of the part's body")
    if name == "LinearPattern":
        if _is_cut(_expand(op.shape)):
            return None
        seed = _solid_boxes(op.shape, part_frame) or []
        d = _vec3(op.direction)
        if np.linalg.norm(d) < 1e-12:
            raise _Unknown("LinearPattern with a zero direction")
        d = d / np.linalg.norm(d)
        step = _val(op.spacing)
        count2 = max(int(_val(op.count2)), 1)
        d2 = np.zeros(3)
        if op.direction2 is not None and count2 > 1:
            d2 = _vec3(op.direction2)
            if np.linalg.norm(d2) < 1e-12:
                raise _Unknown("LinearPattern with a zero direction2")
            d2 = d2 / np.linalg.norm(d2) * _val(op.spacing2)
        return [
            box.transformed(np.eye(3), d * step * i + d2 * j)
            for j in range(count2)
            for i in range(max(int(_val(op.count)), 1))
            for box in seed
        ]
    if name == "PolarPattern":
        if _is_cut(_expand(op.shape)):
            return None
        seed = _solid_boxes(op.shape, part_frame) or []
        count = max(int(_val(op.count)), 1)
        angle = _val(op.angle)
        full = abs(angle - 360.0) < 1e-9
        step = angle / count if full else angle / max(count - 1, 1)
        origin, axis = _vec3(op.axis_origin), _vec3(op.axis_direction)
        out = []
        for i in range(count):
            rot = _rot_about(axis, math.radians(step * i))
            out += [box.transformed(rot, origin - rot @ origin) for box in seed]
        return out
    if name == "MoveBody":
        if _is_cut(_expand(op.shape)):
            return None
        seed = _solid_boxes(op.shape, part_frame) or []
        rot = _rot_about(_vec3(op.rotation_axis), math.radians(_val(op.rotation_angle)))
        origin = _vec3(op.rotation_origin)
        shift = origin - rot @ origin + _vec3(op.translation)
        # The unmoved seed stays in the union: conservative if it was moved away.
        return [box.transformed(rot, shift) for box in seed]
    raise _Unknown(f"operation {name}")


# --------------------------------------------------------------------------- #
# Exact box cuts: a straight extrusion of axis-aligned rectangles cuts exactly
# its box, so it can be carved out of axis-aligned body boxes (tenon
# shoulders, rebates, notches). Any other cut is ignored (outer bound kept).
# --------------------------------------------------------------------------- #

_THROUGH = 1e6  # "through all" depth for cut boxes, mm
_MAX_BOXES = 256


def _signed_permutation(r: np.ndarray) -> bool:
    p = np.round(r)
    return bool(
        np.allclose(r, p, atol=1e-9)
        and np.allclose(np.abs(p).sum(axis=0), 1)
        and np.allclose(np.abs(p).sum(axis=1), 1)
    )


def _is_rectangle(shape: Any) -> Optional[tuple[float, float, float, float]]:
    """Bounds of ``shape`` if it is exactly an axis-aligned rectangle."""
    try:
        shape = _expand(shape)
    except _Unknown:
        return None
    if type(shape).__name__ != "Polygon" or len(shape.lines) != 4:
        return None
    pts = [_xy(line.p1) for line in shape.lines] + [
        _xy(line.p2) for line in shape.lines
    ]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    corners = set()
    for x, y in pts:
        if not (
            min(abs(x - x0), abs(x - x1)) < 1e-9
            and min(abs(y - y0), abs(y - y1)) < 1e-9
        ):
            return None
        corners.add((abs(x - x0) < 1e-9, abs(y - y0) < 1e-9))
    if len(corners) != 4 or x1 - x0 < 1e-9 or y1 - y0 < 1e-9:
        return None
    return x0, y0, x1, y1


def _exact_cut_aabbs(
    op: Any, part_frame: Any
) -> Optional[list[tuple[np.ndarray, np.ndarray]]]:
    """Part-frame AABBs removed exactly by ``op``, or ``None`` if not exact."""
    if type(op).__name__ != "Extrusion" or not _is_cut(op):
        return None
    if (
        getattr(op, "thin_wall", None) is not None
        or getattr(op, "direction", None) is not None
    ):
        return None
    if getattr(op, "taper", None) is not None and abs(_val(op.taper)) > 1e-12:
        return None
    r, t = _sketch_frame(op.sketch, part_frame)
    if not _signed_permutation(r):
        return None
    start, end = _val(op.start), _val(op.end)
    cond = getattr(getattr(op, "end_condition", None), "value", "BLIND") or "BLIND"
    if cond == "SYMMETRIC":
        start, end = -end / 2.0, end / 2.0
    elif cond == "THROUGH_ALL":
        end = start + (_THROUGH if end >= 0 else -_THROUGH)
    elif cond == "THROUGH_ALL_BOTH":
        start, end = -_THROUGH, _THROUGH
    out = []
    for shape in op.shape:
        rect = _is_rectangle(shape)
        if rect is None:
            return None
        x0, y0, x1, y1 = rect
        pts = np.array(
            [
                r @ np.array([x, y, z]) + t
                for x in (x0, x1)
                for y in (y0, y1)
                for z in (start, end)
            ]
        )
        out.append((pts.min(axis=0), pts.max(axis=0)))
    return out


def _aabb_of(box: OBB) -> Optional[tuple[np.ndarray, np.ndarray]]:
    if not _signed_permutation(box.axes):
        return None
    ext = np.abs(box.axes) @ box.half
    return box.center - ext, box.center + ext


def _subtract_aabb(
    lo: np.ndarray, hi: np.ndarray, c_lo: np.ndarray, c_hi: np.ndarray
) -> list[tuple[np.ndarray, np.ndarray]]:
    """``[lo, hi] − [c_lo, c_hi]`` as up to 6 disjoint boxes."""
    if np.any(c_hi <= lo + _EPS) or np.any(c_lo >= hi - _EPS):
        return [(lo, hi)]
    out = []
    lo, hi = lo.copy(), hi.copy()
    for axis in range(3):
        if c_lo[axis] > lo[axis] + _EPS:
            piece_hi = hi.copy()
            piece_hi[axis] = c_lo[axis]
            out.append((lo.copy(), piece_hi))
            lo[axis] = c_lo[axis]
        if c_hi[axis] < hi[axis] - _EPS:
            piece_lo = lo.copy()
            piece_lo[axis] = c_hi[axis]
            out.append((piece_lo, hi.copy()))
            hi[axis] = c_hi[axis]
    return out


def _carve(boxes: list[OBB], cuts: list[tuple[np.ndarray, np.ndarray]]) -> list[OBB]:
    for c_lo, c_hi in cuts:
        carved: list[OBB] = []
        for box in boxes:
            aabb = _aabb_of(box)
            if aabb is None:
                carved.append(box)  # not axis-aligned: keep the outer bound
                continue
            carved += [
                OBB.from_bounds(lo, hi) for lo, hi in _subtract_aabb(*aabb, c_lo, c_hi)
            ]
        if len(carved) > _MAX_BOXES:
            return boxes  # stop refining; the previous set is still an outer bound
        boxes = carved
    return boxes


def estimate_part_extents(part: Any) -> PartExtents:
    """Bound a part (``Part`` or ``PartRoot``) from its operations.

    Estimated (outer bounds, in the part frame):

    * ``Extrusion`` with ``BLIND`` / ``SYMMETRIC`` end conditions, ``taper``,
      ``thin_wall`` and a custom ``direction`` — and everything that expands
      to one: ``Box``, ``Cylinder``, ``Cone``, ``Hole`` & hole wizards;
    * ``Lathe`` (and ``Torus``), ``Sphere``, ``Wedge``, ruled or two-section
      ``Loft``;
    * ``LinearPattern``, ``PolarPattern``, ``MoveBody``, ``BooleanOperation``
      over estimated operands; ``Shell`` inflates by its thickness;
    * 2D profiles: circles, ellipses, lines, 3-point arcs, Bézier/B-spline
      control polygons, polygons and every rectangle/slot/polygon sugar that
      expands to them, ``Offset2D``, ``Trace``.

    Subtractive operations (``cut=True``, holes), ``Fillet`` / ``Chamfer`` /
    ``FullRound`` / ``Split`` and ``DeleteBodies`` / ``KeepBodies`` never grow
    a part. A straight cut extrusion of
    axis-aligned rectangles (tenon shoulders, notches, rebates) removes exactly
    its box and is carved out of the axis-aligned boxes built before it, so a
    tenoned rail is bounded by its beam box plus a tenon box; other cuts are
    skipped (the outer bound is kept).

    Unknown (the part's ``unknown`` reasons name them): ``THROUGH_ALL`` additive
    extrusions, ``Sweep`` / ``MultiSectionSweep`` / ``Thread``, surfaces
    (``SurfaceLoft``, ``Thicken``, ``Stitch``), sheet metal, ``Mirror``,
    ``Scale``, ``Draft``, ``OffsetFace``, ``Emboss`` / ``Wrap`` / ``Rip``,
    ``Section`` / ``Project`` / ``BoundingBox``, smooth multi-section lofts,
    and ``Spline`` / ``Text`` / ``SVGShape`` profiles. A part with no solid
    operation at all is unknown too.
    """
    explicit = getattr(part, _EXPLICIT_EXTENTS_ATTR, None)
    if explicit is None:
        source = getattr(part, "_source_component", None)
        explicit = (
            getattr(source, _EXPLICIT_EXTENTS_ATTR, None)
            if source is not None
            else None
        )
    if explicit is not None:
        return explicit

    boxes: list[OBB] = []
    inflate = 0.0
    unknown: list[str] = []
    for op in part.operations:
        try:
            if type(op).__name__ == "Shell":
                # Shell may grow outward by at most its thickness.
                inflate += abs(_val(op.thickness))
                continue
            cuts = _exact_cut_aabbs(op, part.frame)
            if cuts is not None:
                boxes = _carve(boxes, cuts)
                continue
            result = _solid_boxes(op, part.frame)
        except _Unknown as exc:
            unknown.append(str(exc))
            continue
        except (AttributeError, TypeError, ValueError, ZeroDivisionError) as exc:
            unknown.append(f"{type(op).__name__}: {exc}")
            continue
        boxes.extend(result or [])
    if not boxes and not unknown:
        unknown.append("no solid operation")
    if inflate:
        boxes = [b.inflated(inflate) for b in boxes]
    return PartExtents(tuple(boxes), tuple(dict.fromkeys(unknown)), "estimated")


ExtentsSpec = Union[
    OBB, Sequence[OBB], tuple[Sequence[float], Sequence[float]], PartExtents
]


def _coerce_extents(spec: ExtentsSpec) -> PartExtents:
    if isinstance(spec, PartExtents):
        return spec
    if isinstance(spec, OBB):
        return PartExtents((spec,), (), "explicit")
    items = list(spec)
    if len(items) == 2 and not isinstance(items[0], OBB) and len(items[0]) == 3:
        return PartExtents((OBB.from_bounds(items[0], items[1]),), (), "explicit")
    if items and all(isinstance(b, OBB) for b in items):
        return PartExtents(tuple(items), (), "explicit")
    raise TypeError(
        "extents must be an OBB, a list of OBBs, or (lo, hi) corners in the part frame"
    )


def set_part_extents(part: Any, extents: Optional[ExtentsSpec]) -> Any:
    """Declare a part's bounding volume (part frame) instead of estimating it.

    ``extents``: an :class:`OBB`, a list of OBBs, or ``(lo, hi)`` corners of an
    axis-aligned box. ``None`` clears the declaration. Returns ``part``.
    """
    if extents is None:
        if hasattr(part, _EXPLICIT_EXTENTS_ATTR):
            object.__delattr__(part, _EXPLICIT_EXTENTS_ATTR)
        return part
    object.__setattr__(part, _EXPLICIT_EXTENTS_ATTR, _coerce_extents(extents))
    return part


# --------------------------------------------------------------------------- #
# Assembly traversal
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Interference:
    """One clash (or undecidable pair) between two parts.

    ``status`` is ``"overlap"`` (bounding volumes interpenetrate by ``depth``
    mm, roughly ``volume`` mm³) or ``"unknown"`` (one side's extents could not
    be estimated; ``reason`` says why, ``depth``/``volume`` are ``None``).
    Paths are ``/``-joined component names from the checked assembly.
    """

    path_a: str
    path_b: str
    status: str
    depth: Optional[float] = None
    volume: Optional[float] = None
    reason: str = ""
    component_a: Any = field(default=None, repr=False, compare=False)
    component_b: Any = field(default=None, repr=False, compare=False)

    @property
    def is_overlap(self) -> bool:
        return self.status == "overlap"


class InterferenceError(ValueError):
    """Raised by ``check_interference(strict=True)`` when parts overlap."""

    def __init__(self, interferences: Sequence[Interference]):
        self.interferences = list(interferences)
        lines = [
            f"  {i.path_a} <-> {i.path_b}: {i.depth:.3f} mm deep, ~{i.volume:.1f} mm³"
            for i in self.interferences
        ]
        super().__init__(
            f"{len(self.interferences)} interference(s) between parts:\n"
            + "\n".join(lines)
            + "\nJoin the parts with a joint/Connection if the contact is intended, "
            "or pass allow=[(a, b)]."
        )


@dataclass
class _Leaf:
    path: str
    root: Any
    source: Any
    rotation: np.ndarray
    translation: np.ndarray
    extents: PartExtents
    world_boxes: list[OBB]


def _display_names(children: Sequence[Any]) -> list[str]:
    """Child names as serialisation will finalise them (non-mutating)."""
    from .compute_functions import _AUTO_SLUG_ATTR

    groups: dict[str, list[int]] = {}
    for idx, child in enumerate(children):
        slug = getattr(child, _AUTO_SLUG_ATTR, None)
        if slug:
            groups.setdefault(slug, []).append(idx)
    names = [child.name.value for child in children]
    for slug, members in groups.items():
        if len(members) > 1:
            for n, idx in enumerate(members, start=1):
                names[idx] = f"{slug}_{n}"
    seen: dict[str, int] = {}
    for idx, name in enumerate(names):  # user names may still collide
        count = seen.get(name, 0)
        seen[name] = count + 1
        if count:
            names[idx] = f"{name}[{count}]"
    return names


def _walk(
    assembly: Any,
) -> tuple[list[_Leaf], dict[int, set[int]], list[Any], dict[str, set[int]]]:
    """Leaves, component-id -> leaf indices, every (sub)assembly object, and
    path -> leaf indices (for parts and sub-assemblies)."""
    from .compute_functions import _SOURCE_COMPONENT_ATTR, _convert_component_to_root
    from .gen.models import AssemblyRoot, PartRoot

    leaves: list[_Leaf] = []
    members: dict[int, set[int]] = {}
    assemblies: list[Any] = [assembly]
    paths: dict[str, set[int]] = {}

    def register(obj: Any, idxs: set[int]) -> None:
        if obj is not None:
            members.setdefault(id(obj), set()).update(idxs)

    def visit(children: Sequence[Any], prefix: str) -> set[int]:
        collected: set[int] = set()
        for child, name in zip(children, _display_names(children)):
            path = f"{prefix}{name}"
            source = getattr(child, _SOURCE_COMPONENT_ATTR, None)
            if isinstance(child, AssemblyRoot):
                # Re-sync with the live sub-assembly (as to_dag does), so
                # components added after it was placed are seen.
                _convert_component_to_root(child)
                assemblies.append(source if source is not None else child)
                idxs = visit(child.components, path + "/")
            elif isinstance(child, PartRoot):
                t, q = tf_relative_to_frame(child.frame, assembly.frame)
                rot, trans = _rotation(q), np.asarray(t, dtype=float)
                extents = estimate_part_extents(child)
                leaves.append(
                    _Leaf(
                        path,
                        child,
                        source,
                        rot,
                        trans,
                        extents,
                        [b.transformed(rot, trans) for b in extents.boxes],
                    )
                )
                idxs = {len(leaves) - 1}
            else:
                continue
            register(child, idxs)
            register(source, idxs)
            paths[path] = idxs
            collected |= idxs
        return collected

    all_idxs = visit(list(assembly.components), "")
    register(assembly, all_idxs)
    return leaves, members, assemblies, paths


def _owner(anchor: Any) -> Any:
    return getattr(anchor, "_anchor_owner", None)


def _allowed_from_design(
    assemblies: Sequence[Any], members: dict[int, set[int]]
) -> set[frozenset[int]]:
    from .compute_functions import _APPLIED_CONNECTIONS_ATTR

    allowed: set[frozenset[int]] = set()

    def allow_group(owners: Sequence[Any]) -> None:
        sets = [members.get(id(o), set()) for o in owners if o is not None]
        for i in range(len(sets)):
            for j in range(i + 1, len(sets)):
                a, b = sets[i], sets[j]
                if not a or not b or a <= b or b <= a:
                    continue  # ground joints / a component vs. its own parent
                for x in a:
                    for y in b:
                        if x != y:
                            allowed.add(frozenset((x, y)))

    for asm in assemblies:
        for joint in getattr(asm, "joints", None) or []:
            allow_group([_owner(joint.parent_anchor), _owner(joint.child_anchor)])
        for conn in getattr(asm, _APPLIED_CONNECTIONS_ATTR, None) or []:
            owners = []
            if conn.joint is not None:
                owners += [
                    _owner(conn.joint.parent_anchor),
                    _owner(conn.joint.child_anchor),
                ]
            owners += [_owner(m.anchor) for m in conn.modifiers]
            unique = list({id(o): o for o in owners if o is not None}.values())
            allow_group(unique)
    return allowed


def _resolve_ref(
    ref: Any, members: dict[int, set[int]], paths: dict[str, set[int]]
) -> set[int]:
    if isinstance(ref, str):
        key = ref.strip("/")
        if key in paths:
            return paths[key]
        raise ValueError(
            f"allow/extents: no component at path '{ref}' (known: {sorted(paths)})"
        )
    idxs = members.get(id(ref))
    if idxs is None:
        raise ValueError(
            f"allow/extents: {type(ref).__name__} "
            f"'{getattr(getattr(ref, 'name', None), 'value', ref)}' is not in this assembly"
        )
    return idxs


def _user_allowed(
    allow: Optional[Iterable[Any]],
    members: dict[int, set[int]],
    paths: dict[str, set[int]],
) -> tuple[set[frozenset[int]], set[int]]:
    pairs: set[frozenset[int]] = set()
    ignored: set[int] = set()
    for item in allow or []:
        if isinstance(item, (tuple, list)) and len(item) == 2:
            a = _resolve_ref(item[0], members, paths)
            b = _resolve_ref(item[1], members, paths)
            pairs |= {frozenset((x, y)) for x in a for y in b if x != y}
        else:
            ignored |= _resolve_ref(item, members, paths)
    return pairs, ignored


# --------------------------------------------------------------------------- #
# Exact mode: real solids, meshed and intersected
# --------------------------------------------------------------------------- #

#: A triangle mesh in the PART frame: vertices (n, 3) mm, triangles (m, 3) indices.
Mesh = tuple[np.ndarray, np.ndarray]
#: Meshes one placed part (its ``PartRoot``); see :func:`kernel_api_mesher`.
Mesher = Callable[[Any], Mesh]

#: Vertices closer than this (mm) are welded before the boolean: kernels emit
#: per-face vertex copies, manifold3d needs a shared-vertex closed mesh.
_WELD_TOL = 1e-6

#: Tessellation the default exact-mode mesher asks the kernel for: chord error
#: ≤ 0.01 mm (the viewer default is 1 mm / 0.2 rad, far too coarse to compare
#: coincident curved faces — a shaft in a same-size bore).
FINE_MESH_CONFIG = {"tolerance": 0.01, "angularTolerance": 0.05}

#: Exact mode ignores shared regions thinner than this (mm): what's left where
#: two tessellations of the SAME curved surface (a line-to-line fit) cross.
#: Twice :data:`FINE_MESH_CONFIG`'s chord error.
DEFAULT_DEPTH_TOL = 0.02


def kernel_api_mesher(
    client: Any = None, mesh_config: Optional[dict[str, float]] = None
) -> Mesher:
    """Mesh each part through the kernel API (``KernelApiClient``; its base URL
    comes from ``CAD_COMPILE_API_BASE_URL`` / ``CADBUILDR_KERNEL_API_BASE_URL``),
    at :data:`FINE_MESH_CONFIG` unless ``mesh_config`` says otherwise. The
    kernel returns a part's mesh in the part's own frame."""
    config = dict(mesh_config or FINE_MESH_CONFIG)

    def mesh(part: Any) -> Mesh:
        from .coms.kernel_api import KernelApiClient
        from .dag_utils import show_dag

        api = client or KernelApiClient()
        out = api.compile_mesh(dag=show_dag(part), mesh_config=config)
        store = (out.get("mesh") or out).get("store") or {}
        geometries = []
        for entry in store.values():
            data = entry.get("data", entry) if isinstance(entry, dict) else None
            if isinstance(data, dict) and data.get("faces"):
                geometries.append(data["faces"])
        if len(geometries) != 1:
            raise ValueError(
                f"kernel returned {len(geometries)} meshes for part "
                f"'{part.name.value}' (expected 1)"
            )
        faces = geometries[0]
        return (
            np.asarray(faces["vertices"], dtype=float).reshape(-1, 3),
            np.asarray(faces["triangles"], dtype=np.int64).reshape(-1, 3),
        )

    return mesh


def _manifold3d() -> Any:
    try:
        import manifold3d
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError(
            "check_interference(exact=True) needs manifold3d: "
            "pip install 'cadbuildr-foundation[exact]'"
        ) from exc
    return manifold3d


def _solid(vertices: np.ndarray, triangles: np.ndarray, label: str) -> Any:
    """A manifold3d solid from a closed triangle mesh (vertices welded)."""
    m3d = _manifold3d()
    verts = np.asarray(vertices, dtype=float).reshape(-1, 3)
    tris = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
    keys = np.round(verts / _WELD_TOL).astype(np.int64)
    _, first, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
    welded = verts[first]
    tris = inverse.reshape(-1)[tris]
    tris = tris[
        (tris[:, 0] != tris[:, 1])
        & (tris[:, 1] != tris[:, 2])
        & (tris[:, 0] != tris[:, 2])
    ]
    solid = m3d.Manifold(
        m3d.Mesh(
            vert_properties=welded.astype(np.float32),
            tri_verts=tris.astype(np.uint32),
        )
    )
    if solid.status() != m3d.Error.NoError:
        raise ValueError(f"{label}: mesh is not a closed solid ({solid.status()})")
    return solid


def solid_overlap(a: Mesh, b: Mesh) -> tuple[float, float]:
    """``(volume mm³, depth mm)`` shared by two closed meshes given in the same
    frame. ``depth`` is the smallest extent of the shared region's bounding
    box — how far one solid reaches into the other."""
    shared = _solid(*a, "a") ^ _solid(*b, "b")
    volume = float(shared.volume())
    if volume <= 0.0:
        return 0.0, 0.0
    box = shared.bounding_box()
    return volume, float(min(box[3] - box[0], box[4] - box[1], box[5] - box[2]))


def _depth_in_frame(shared: Any, rotation: np.ndarray) -> float:
    """Smallest extent of the shared region, measured along the axes of a
    part's own frame (world axes would inflate it for rotated parts)."""
    inv = np.asarray(rotation, dtype=float).T
    local = shared.transform(np.hstack([inv, np.zeros((3, 1))]).tolist())
    box = local.bounding_box()
    return float(min(box[3] - box[0], box[4] - box[1], box[5] - box[2]))


def _exact_overlaps(
    leaves: Sequence[_Leaf],
    allowed: set[frozenset[int]],
    ignored: set[int],
    mesher: Mesher,
    tolerance: float,
    volume_tol: float,
    depth_tol: float,
) -> tuple[list[Interference], list[Interference]]:
    solids: dict[int, Any] = {}
    boxes: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    failed: dict[int, str] = {}
    for idx, leaf in enumerate(leaves):
        if idx in ignored:
            continue
        try:
            verts, tris = mesher(leaf.root)
            world = np.asarray(verts, dtype=float) @ leaf.rotation.T + leaf.translation
            solids[idx] = _solid(world, tris, leaf.path)
            boxes[idx] = (world.min(axis=0), world.max(axis=0))
        except Exception as exc:  # report, don't guess
            failed[idx] = f"{leaf.path}: could not mesh ({exc})"

    overlaps: list[Interference] = []
    unknowns: list[Interference] = []
    for i in range(len(leaves)):
        if i in ignored:
            continue
        for j in range(i + 1, len(leaves)):
            if j in ignored or frozenset((i, j)) in allowed:
                continue
            a, b = leaves[i], leaves[j]
            if i in failed or j in failed:
                unknowns.append(
                    Interference(
                        a.path,
                        b.path,
                        "unknown",
                        reason="; ".join(failed[k] for k in (i, j) if k in failed),
                        component_a=a.source or a.root,
                        component_b=b.source or b.root,
                    )
                )
                continue
            (lo_a, hi_a), (lo_b, hi_b) = boxes[i], boxes[j]
            if np.any(np.minimum(hi_a, hi_b) - np.maximum(lo_a, lo_b) <= 0.0):
                continue
            shared = solids[i] ^ solids[j]
            volume = float(shared.volume())
            if volume <= volume_tol:
                continue
            # Thickness of the shared region (2V/A, exact for a thin sheet):
            # coincident tessellated faces leave a sheet a few microns thick
            # that wraps a whole shaft, so its bounding box says nothing.
            area = float(shared.surface_area())
            if area > 0.0 and 2.0 * volume / area <= depth_tol:
                continue
            depth = _depth_in_frame(shared, a.rotation)
            if depth <= tolerance:
                continue
            overlaps.append(
                Interference(
                    a.path,
                    b.path,
                    "overlap",
                    depth=depth,
                    volume=volume,
                    reason="solids overlap",
                    component_a=a.source or a.root,
                    component_b=b.source or b.root,
                )
            )
    return overlaps, unknowns


def check_interference(
    assembly: Any,
    tolerance: float = 0.0,
    allow: Optional[Iterable[Any]] = None,
    *,
    extents: Optional[dict[Any, ExtentsSpec]] = None,
    strict: bool = False,
    include_unknown: bool = True,
    exact: bool = False,
    volume_tol: float = 1e-3,
    mesher: Optional[Mesher] = None,
    depth_tol: float = DEFAULT_DEPTH_TOL,
) -> list[Interference]:
    """Find parts of ``assembly`` whose bounding volumes interpenetrate.

    Args:
        tolerance: overlap depth (mm) to accept; pairs are reported when the
            boxes penetrate deeper than this. Touching faces never count.
        allow: extra intended contacts. Each item is a pair ``(a, b)`` (both
            sides: a Part/Assembly object, its placed root, or a component
            path such as ``"frame/leg_1"``; a sub-assembly stands for all its
            parts) or a single component to leave out of the check entirely.
        extents: per-part bounding volumes overriding estimation, keyed like
            ``allow`` items (part-frame ``OBB``, list of OBBs, or ``(lo, hi)``).
        strict: raise :class:`InterferenceError` if any overlap is found.
        include_unknown: also return ``"unknown"`` entries for pairs involving
            a part whose extents could not be estimated (or, in exact mode,
            meshed).
        exact: compare the real solids (meshed, intersected with manifold3d)
            instead of bounding boxes. Jointed / connected pairs are checked
            too; only ``allow=`` exempts a pair. ``extents=`` is ignored.
        volume_tol: exact mode: shared volume (mm³) to accept.
        mesher: exact mode: ``mesher(part_root) -> (vertices, triangles)`` in
            the part frame. Default: :func:`kernel_api_mesher` (fine
            tessellation, :data:`FINE_MESH_CONFIG`).
        depth_tol: exact mode: ignore shared regions thinner than this (mm,
            2·volume/area) — the slivers two tessellations of one curved
            surface leave in a line-to-line fit (shaft in a same-size bore).
            Default :data:`DEFAULT_DEPTH_TOL`; raise it with a coarser mesher.

    Returns:
        Overlaps first (deepest first), then unknown pairs, as
        :class:`Interference` records.
    """
    leaves, members, assemblies, paths = _walk(assembly)
    if exact:
        user_pairs, ignored = _user_allowed(allow, members, paths)
        overlaps, unknowns = _exact_overlaps(
            leaves,
            user_pairs,
            ignored,
            mesher or kernel_api_mesher(),
            tolerance,
            volume_tol,
            depth_tol,
        )
        overlaps.sort(key=lambda r: -(r.volume or 0.0))
        if strict and overlaps:
            raise InterferenceError(overlaps)
        return overlaps + (unknowns if include_unknown else [])
    for ref, spec in (extents or {}).items():
        ext = _coerce_extents(spec)
        for idx in _resolve_ref(ref, members, paths):
            leaf = leaves[idx]
            leaf.extents = ext
            leaf.world_boxes = [
                b.transformed(leaf.rotation, leaf.translation) for b in ext.boxes
            ]

    allowed = _allowed_from_design(assemblies, members)
    user_pairs, ignored = _user_allowed(allow, members, paths)
    allowed |= user_pairs

    overlaps: list[Interference] = []
    unknowns: list[Interference] = []
    for i in range(len(leaves)):
        if i in ignored:
            continue
        a = leaves[i]
        for j in range(i + 1, len(leaves)):
            if j in ignored or frozenset((i, j)) in allowed:
                continue
            b = leaves[j]
            if not (a.extents.known and b.extents.known):
                if include_unknown:
                    reasons = [
                        f"{leaf.path}: {', '.join(leaf.extents.unknown)}"
                        for leaf in (a, b)
                        if not leaf.extents.known
                    ]
                    unknowns.append(
                        Interference(
                            a.path,
                            b.path,
                            "unknown",
                            reason="; ".join(reasons),
                            component_a=a.source or a.root,
                            component_b=b.source or b.root,
                        )
                    )
                continue
            depth, volume = 0.0, 0.0
            for box_a in a.world_boxes:
                for box_b in b.world_boxes:
                    pen = obb_penetration(box_a, box_b)
                    if pen > tolerance + _EPS:
                        depth = max(depth, pen)
                        volume += obb_overlap_volume(box_a, box_b)
            if depth > 0.0:
                overlaps.append(
                    Interference(
                        a.path,
                        b.path,
                        "overlap",
                        depth=depth,
                        volume=volume,
                        reason="bounding volumes overlap",
                        component_a=a.source or a.root,
                        component_b=b.source or b.root,
                    )
                )
    overlaps.sort(key=lambda r: -(r.depth or 0.0))
    if strict and overlaps:
        raise InterferenceError(overlaps)
    return overlaps + unknowns


def _assembly_check_interference(
    self: Any,
    tolerance: float = 0.0,
    allow: Optional[Iterable[Any]] = None,
    *,
    extents: Optional[dict[Any, ExtentsSpec]] = None,
    strict: bool = False,
    include_unknown: bool = True,
    exact: bool = False,
    volume_tol: float = 1e-3,
    mesher: Optional[Mesher] = None,
    depth_tol: float = DEFAULT_DEPTH_TOL,
) -> list[Interference]:
    return check_interference(
        self,
        tolerance,
        allow,
        extents=extents,
        strict=strict,
        include_unknown=include_unknown,
        exact=exact,
        volume_tol=volume_tol,
        mesher=mesher,
        depth_tol=depth_tol,
    )


_assembly_check_interference.__doc__ = check_interference.__doc__


def _install() -> None:
    from .gen.models import Assembly, Part

    setattr(Assembly, "check_interference", _assembly_check_interference)
    setattr(Part, "set_extents", lambda self, extents: set_part_extents(self, extents))


_install()
