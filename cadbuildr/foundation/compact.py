"""Compact geometry: profiles stored as one node, rings, hole patterns.

Libraries that draw long outlines (rack teeth, grid plates, flat-pack
panels, cam and mechanism profiles) used to build one ``Point`` (+ two
``FloatParameter``) and one ``Line``/``Arc`` per vertex. ``CompactPolygon`` /
``CompactPolyline`` keep the whole outline in ONE node: a flat coordinate list
plus an optional per-edge *bulge* that turns an edge into a true circular arc
(bulge = tan(sweep / 4), positive = counter-clockwise; DXF LWPOLYLINE).

Kernels do not read the compact nodes natively yet, so serialization lowers
them to ``CustomClosedShape`` / ``CustomOpenShape`` of ``Line`` and ``Arc``
(``@expand``). A kernel that learns them only needs to be added to
``show_dag(valid_types=[*DEFAULT_VALID_TYPES, "CompactPolygon", ...])``.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Optional, Sequence

from .gen.runtime import register_compute_fn, register_method_fn

_EPS = 1e-9


class CompactProfileError(ValueError):
    """A CompactPolygon / CompactPolyline with unusable coordinates or bulges."""


def bulge_from_sweep(sweep_deg: float) -> float:
    """Bulge of an arc edge sweeping ``sweep_deg`` degrees (+ = counter-clockwise)."""
    return math.tan(math.radians(sweep_deg) / 4.0)


def _vertices(coords: Sequence[float], what: str) -> list[tuple[float, float]]:
    vals = [float(getattr(c, "value", c)) for c in coords]
    if len(vals) % 2:
        raise CompactProfileError(
            f"{what}.coords must be a flat [x0, y0, x1, y1, ...] list; got an odd "
            f"length {len(vals)}"
        )
    return [(vals[i], vals[i + 1]) for i in range(0, len(vals), 2)]


def _edge_bulges(
    bulges: Optional[Sequence[float]], n_edges: int, what: str
) -> list[float]:
    if not bulges:
        return [0.0] * n_edges
    out = [float(getattr(b, "value", b)) for b in bulges]
    if len(out) != n_edges:
        raise CompactProfileError(
            f"{what}.bulges needs one value per edge ({n_edges}); got {len(out)}"
        )
    for i, b in enumerate(out):
        if not math.isfinite(b):
            raise CompactProfileError(f"{what}.bulges[{i}] is not finite")
    return out


def arc_midpoint(
    a: tuple[float, float], b: tuple[float, float], bulge: float
) -> tuple[float, float]:
    """Point halfway along the arc from ``a`` to ``b`` with ``bulge``.

    The sagitta is bulge × chord / 2; a positive (counter-clockwise) bulge puts
    the arc on the right of the chord direction a → b.
    """
    dx, dy = b[0] - a[0], b[1] - a[1]
    chord = math.hypot(dx, dy)
    s = bulge * chord / 2.0
    return ((a[0] + b[0]) / 2.0 + s * dy / chord, (a[1] + b[1]) / 2.0 - s * dx / chord)


def edge_primitives(
    sketch: Any,
    vertices: Sequence[tuple[float, float]],
    bulges: Sequence[float],
    closed: bool,
) -> list:
    """Lines and three-point Arcs for the edges of a compact profile.

    Vertex Points are shared between neighbouring edges, so the lowered shape
    has one Point per vertex (plus one per arc midpoint)."""
    from .gen.models import Arc, FloatParameter, Line, Point

    def pt(x: float, y: float) -> Any:
        return Point(
            sketch=sketch, x=FloatParameter(value=x), y=FloatParameter(value=y)
        )

    points = [pt(x, y) for x, y in vertices]
    n = len(vertices)
    out: list = []
    for i in range(n if closed else n - 1):
        j = (i + 1) % n
        if abs(bulges[i]) <= _EPS:
            out.append(Line(p1=points[i], p2=points[j]))
        else:
            mid = arc_midpoint(vertices[i], vertices[j], bulges[i])
            out.append(Arc(p1=points[i], p2=pt(*mid), p3=points[j]))
    return out


def validate_profile(
    coords: Sequence[float], bulges: Optional[Sequence[float]], closed: bool
) -> tuple[list[tuple[float, float]], list[float]]:
    """Vertices and per-edge bulges of a compact profile, or a
    ``CompactProfileError``. Pure arithmetic: builds no nodes."""
    what = "CompactPolygon" if closed else "CompactPolyline"
    vertices = _vertices(coords, what)
    least = 3 if closed else 2
    if len(vertices) < least:
        raise CompactProfileError(
            f"{what} needs at least {least} vertices; got {len(vertices)}"
        )
    n = len(vertices)
    n_edges = n if closed else n - 1
    edge_bulges = _edge_bulges(bulges, n_edges, what)
    for i in range(n_edges):
        a, b = vertices[i], vertices[(i + 1) % n]
        if math.hypot(b[0] - a[0], b[1] - a[1]) <= _EPS:
            raise CompactProfileError(
                f"{what}: edge {i} from vertex {i} to vertex {(i + 1) % n} has "
                f"zero length at ({a[0]:g}, {a[1]:g})"
            )
    return vertices, edge_bulges


@register_compute_fn("compute_compact_polygon_primitives")
def compute_compact_polygon_primitives(inst: Any, field_name: str, meta: dict) -> list:
    vertices, bulges = validate_profile(inst.coords, inst.bulges, True)
    return edge_primitives(inst.sketch, vertices, bulges, True)


@register_compute_fn("compute_compact_polyline_primitives")
def compute_compact_polyline_primitives(inst: Any, field_name: str, meta: dict) -> list:
    vertices, bulges = validate_profile(inst.coords, inst.bulges, False)
    return edge_primitives(inst.sketch, vertices, bulges, False)


def _split_points(
    points: Iterable[Any], closed: bool, what: str
) -> tuple[list[float], Optional[list[float]]]:
    """(x, y) / (x, y, bulge) tuples (or Points) → flat coords + bulges."""
    verts: list[tuple[float, float, float]] = []
    for raw in points:
        if hasattr(raw, "x") and hasattr(raw, "y") and hasattr(raw, "sketch"):
            verts.append((float(raw.x.value), float(raw.y.value), 0.0))
            continue
        vals = list(raw.tolist() if hasattr(raw, "tolist") else raw)
        if len(vals) not in (2, 3):
            raise CompactProfileError(
                f"{what}.from_points takes (x, y) or (x, y, bulge); got {tuple(vals)!r}"
            )
        verts.append(
            (float(vals[0]), float(vals[1]), float(vals[2]) if len(vals) == 3 else 0.0)
        )
    if (
        closed
        and len(verts) > 1
        and abs(verts[0][0] - verts[-1][0]) <= _EPS
        and abs(verts[0][1] - verts[-1][1]) <= _EPS
    ):
        verts.pop()  # repeated closing point
    coords = [c for x, y, _ in verts for c in (x, y)]
    bulges = [b for _, _, b in verts]
    if not closed:
        bulges = bulges[:-1]
    return coords, (bulges if any(abs(b) > _EPS for b in bulges) else None)


@register_method_fn("compact_polygon_from_points")
def compact_polygon_from_points(inst: Any, sketch: Any, points: Any) -> Any:
    """Closed ``CompactPolygon`` through ``points`` on ``sketch``; a third value
    on a point is the bulge of the edge leaving it."""
    from .gen.models import CompactPolygon

    coords, bulges = _split_points(points, True, "CompactPolygon")
    shape = CompactPolygon(sketch=sketch, coords=coords, bulges=bulges)
    validate_profile(coords, bulges, True)  # fail here, not at serialization
    return shape


@register_method_fn("compact_polyline_from_points")
def compact_polyline_from_points(inst: Any, sketch: Any, points: Any) -> Any:
    """Open ``CompactPolyline`` through ``points``; a third value on a point is
    the bulge of the edge leaving it (ignored on the last point)."""
    from .gen.models import CompactPolyline

    coords, bulges = _split_points(points, False, "CompactPolyline")
    shape = CompactPolyline(sketch=sketch, coords=coords, bulges=bulges)
    validate_profile(coords, bulges, False)
    return shape


def ring(
    center: Any,
    outer_radius: float,
    inner_radius: float,
    depth: float,
    *,
    start: float = 0.0,
    cut: bool = False,
) -> Any:
    """Annulus extruded from ``start`` to ``depth`` along the sketch normal, as
    ONE Extrusion: the outer circle with a ``thin_wall`` band of
    ``outer_radius - inner_radius``. ``cut=True`` cuts a ring groove in one
    operation (no cut, refill, recut).

        part.add_operation(ring(s.origin, 20, 16, -2, cut=True))  # O-ring groove
    """
    from .gen.models import Circle, Extrusion

    outer_radius, inner_radius = float(outer_radius), float(inner_radius)
    if not 0.0 < inner_radius < outer_radius:
        raise CompactProfileError(
            f"ring: need 0 < inner_radius < outer_radius; got inner {inner_radius:g}, "
            f"outer {outer_radius:g}"
        )
    return Extrusion(
        Circle(center, outer_radius),
        end=float(depth),
        start=float(start),
        cut=cut,
        thin_wall=outer_radius - inner_radius,
    )
