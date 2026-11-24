"""Sketch-level helpers: patterns and mirrors of 2D shapes.

These build ordinary sketch shapes (they don't add DAG nodes), so the results
can be extruded, lofted, cut, … like anything drawn by hand.
"""

from __future__ import annotations

import math
from typing import Any

from .gen.models import (
    Arc,
    BSpline,
    Bezier,
    Circle,
    CustomClosedShape,
    CustomOpenShape,
    Ellipse,
    EllipseArc,
    Line,
    Point,
    Polygon,
    Spline,
)


def _movable(shape: Any) -> Any:
    """Shapes with translate/rotate are used as-is; polygon-like shapes without
    them (Rectangle, Square, Triangle, ...) are re-expressed as a Polygon."""
    if hasattr(type(shape), "rotate") and hasattr(type(shape), "translate"):
        return shape
    lines = getattr(shape, "lines", None)
    if lines:
        return Polygon(lines=list(lines))
    raise TypeError(
        f"{type(shape).__name__} can't be copied: it has no translate/rotate and no lines"
    )


def linear_copies(shape: Any, dx: float, dy: float, count: int) -> list[Any]:
    """`count` copies of `shape`, each shifted (dx, dy) from the previous one.
    The first item is the original shape."""
    if count < 1:
        raise ValueError("linear_copies: count must be >= 1")
    base = _movable(shape)
    return [shape] + [base.translate(dx * i, dy * i) for i in range(1, count)]


def polar_copies(
    shape: Any, center: Point, count: int, angle: float = 360.0
) -> list[Any]:
    """`count` copies of `shape` rotated about `center`. A full 360° spreads them
    evenly; a smaller `angle` puts the first at 0° and the last at `angle`.
    The first item is the original shape."""
    if count < 1:
        raise ValueError("polar_copies: count must be >= 1")
    step = angle / count if abs(angle - 360.0) < 1e-9 else angle / max(count - 1, 1)
    base = _movable(shape)
    return [shape] + [
        base.rotate(math.radians(step * i), center) for i in range(1, count)
    ]


def _mirror_xy(x: float, y: float, line: Line) -> tuple[float, float]:
    ax, ay = line.p1.x.value, line.p1.y.value
    bx, by = line.p2.x.value, line.p2.y.value
    dx, dy = bx - ax, by - ay
    n = math.hypot(dx, dy)
    if n < 1e-12:
        raise ValueError("mirror: the mirror line is degenerate")
    ux, uy = dx / n, dy / n
    px, py = x - ax, y - ay
    d = px * ux + py * uy
    fx, fy = ax + d * ux, ay + d * uy
    return 2 * fx - x, 2 * fy - y


def mirror_point(point: Point, line: Line) -> Point:
    """Reflection of `point` across `line` (same sketch)."""
    x, y = _mirror_xy(point.x.value, point.y.value, line)
    return Point(point.sketch, x, y)


def _mirror_vector(vx: float, vy: float, line: Line) -> tuple[float, float]:
    """A direction (not a point) reflected across `line`'s direction."""
    dx = line.p2.x.value - line.p1.x.value
    dy = line.p2.y.value - line.p1.y.value
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    d = vx * ux + vy * uy
    return 2 * d * ux - vx, 2 * d * uy - vy


def _axis_parallel(line: Line) -> str:
    """'x' or 'y' if the mirror line runs along a sketch axis, else ''."""
    dx = line.p2.x.value - line.p1.x.value
    dy = line.p2.y.value - line.p1.y.value
    if abs(dy) <= 1e-12 * max(1.0, abs(dx)):
        return "x"
    if abs(dx) <= 1e-12 * max(1.0, abs(dy)):
        return "y"
    return ""


def _mirror_angle(angle: float, axis: str) -> float:
    # Across a line along x, angles flip sign; along y, they go to pi - angle.
    return -angle if axis == "x" else math.pi - angle


def _mirror_ellipse(shape: Any, line: Line, reverse: bool = False) -> Any:
    axis = _axis_parallel(line)
    if not axis:
        raise TypeError(
            f"mirror: an {type(shape).__name__} (axes along x / y) mirrors only across "
            "a line along the sketch x or y axis; mirroring it across a slanted line "
            "would tilt its axes, which foundation ellipses can't express"
        )
    center = mirror_point(shape.center, line)
    if isinstance(shape, Ellipse):
        return Ellipse(center, shape.a.value, shape.b.value)
    a0 = _mirror_angle(shape.start_angle.value, axis)
    a1 = _mirror_angle(shape.end_angle.value, axis)
    if reverse:
        a0, a1 = a1, a0
    return EllipseArc(center, shape.a.value, shape.b.value, a0, a1)


def _mirror_points(points: list[Point], line: Line, reverse: bool) -> list[Point]:
    pts = [mirror_point(p, line) for p in points]
    return pts[::-1] if reverse else pts


def _mirror_tangent(t: Any, line: Line) -> Any:
    if t is None:
        return None
    x, y = _mirror_vector(t.x.value, t.y.value, line)
    return Point(t.sketch, x, y)


def _negated(t: Any) -> Any:
    return None if t is None else Point(t.sketch, -t.x.value, -t.y.value)


def _mirror_primitive(prim: Any, line: Line, reverse: bool) -> Any:
    """One boundary element mirrored; `reverse` also runs it backwards (to keep
    a chain's winding when the chain itself is reversed)."""
    if isinstance(prim, Line):
        a, b = mirror_point(prim.p1, line), mirror_point(prim.p2, line)
        return Line(b, a) if reverse else Line(a, b)
    if isinstance(prim, Arc):
        a, m, b = (mirror_point(p, line) for p in (prim.p1, prim.p2, prim.p3))
        return Arc(b, m, a) if reverse else Arc(a, m, b)
    if isinstance(prim, Spline):
        t0 = _mirror_tangent(prim.start_tangent, line)
        t1 = _mirror_tangent(prim.end_tangent, line)
        if reverse:
            # Running backwards, the end tangent (negated) leads.
            t0, t1 = _negated(t1), _negated(t0)
        kw = {
            k: v
            for k, v in (("start_tangent", t0), ("end_tangent", t1))
            if v is not None
        }
        return Spline(_mirror_points(prim.points, line, reverse), **kw)
    if isinstance(prim, Bezier):
        return Bezier(_mirror_points(prim.points, line, reverse))
    if isinstance(prim, BSpline):
        return BSpline(_mirror_points(prim.points, line, reverse), prim.degree.value)
    if isinstance(prim, EllipseArc):
        return _mirror_ellipse(prim, line, reverse)
    raise TypeError(f"mirror: unsupported boundary element {type(prim).__name__}")


def mirror(shape: Any, line: Line) -> Any:
    """Mirror image of a sketch shape across `line` (a Line of the same sketch).

    Points, lines, arcs, splines (Spline / Bezier / BSpline), circles and
    custom open / closed shapes keep their type (element by element, so the
    mirror of a counter-clockwise outline runs clockwise). Polygon-like shapes (anything with a
    `lines` list: Polygon, Rectangle, Square, Triangle, Hexagon, ...) come back
    as a Polygon. Ellipses and elliptical arcs mirror across a line along the
    sketch x or y axis.
    """
    if isinstance(shape, Point):
        return mirror_point(shape, line)
    if isinstance(shape, Circle):
        return Circle(mirror_point(shape.center, line), shape.radius.value)
    if isinstance(shape, (Ellipse, EllipseArc)):
        return _mirror_ellipse(shape, line)
    if isinstance(shape, (Line, Arc, Spline, Bezier, BSpline)):
        return _mirror_primitive(shape, line, reverse=False)
    if isinstance(shape, CustomClosedShape):
        # Mirrored in place, element by element (a smooth Spline isn't the same
        # curve when traced backwards, so the order is kept).
        return CustomClosedShape(
            [_mirror_primitive(p, line, False) for p in shape.primitives]
        )
    if isinstance(shape, CustomOpenShape):
        return CustomOpenShape(
            [_mirror_primitive(p, line, False) for p in shape.primitives]
        )
    lines = getattr(shape, "lines", None)
    if lines:
        # Reverse the order so the mirrored outline keeps a consistent winding.
        mirrored = [
            Line(mirror_point(l.p2, line), mirror_point(l.p1, line))
            for l in reversed(lines)
        ]
        return Polygon(lines=mirrored)
    raise TypeError(f"mirror: unsupported shape {type(shape).__name__}")


def _xy(p: Point) -> tuple[float, float]:
    return p.x.value, p.y.value


def extend(line: Line, start: float = 0.0, end: float = 0.0) -> Line:
    """`line` lengthened by `start` before p1 and `end` past p2 (negative values shorten it)."""
    (ax, ay), (bx, by) = _xy(line.p1), _xy(line.p2)
    n = math.hypot(bx - ax, by - ay)
    if n < 1e-12:
        raise ValueError("extend: degenerate line")
    ux, uy = (bx - ax) / n, (by - ay) / n
    sk = line.p1.sketch
    return Line(
        Point(sk, ax - ux * start, ay - uy * start),
        Point(sk, bx + ux * end, by + uy * end),
    )


def intersect(l1: Line, l2: Line) -> Point:
    """Intersection of the infinite lines through `l1` and `l2`."""
    (x1, y1), (x2, y2) = _xy(l1.p1), _xy(l1.p2)
    (x3, y3), (x4, y4) = _xy(l2.p1), _xy(l2.p2)
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        raise ValueError("intersect: the lines are parallel")
    a = x1 * y2 - y1 * x2
    b = x3 * y4 - y3 * x4
    return Point(
        l1.p1.sketch,
        (a * (x3 - x4) - (x1 - x2) * b) / den,
        (a * (y3 - y4) - (y1 - y2) * b) / den,
    )


def trim_corner(l1: Line, l2: Line) -> tuple[Line, Line]:
    """Trim or extend two lines so they meet exactly at their intersection
    (each keeps the endpoint farther from the corner)."""
    c = intersect(l1, l2)
    cx, cy = _xy(c)

    def keep_far(line: Line) -> Line:
        d1 = math.hypot(line.p1.x.value - cx, line.p1.y.value - cy)
        d2 = math.hypot(line.p2.x.value - cx, line.p2.y.value - cy)
        return Line(line.p1, c) if d1 >= d2 else Line(c, line.p2)

    return keep_far(l1), keep_far(l2)
