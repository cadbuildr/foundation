"""Sketch-level helpers: patterns and mirrors of 2D shapes.

These build ordinary sketch shapes (they don't add DAG nodes), so the results
can be extruded, lofted, cut, … like anything drawn by hand.
"""

from __future__ import annotations

import math
from typing import Any

from .gen.models import Circle, Line, Point, Polygon


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


def mirror(shape: Any, line: Line) -> Any:
    """Mirror image of a Point, Line, Circle or Polygon-like shape across `line`.

    Polygon-like means anything with a `lines` list (Polygon, Rectangle,
    Square, Triangle, ...); the mirror is returned as a Polygon.
    """
    if isinstance(shape, Point):
        return mirror_point(shape, line)
    if isinstance(shape, Line):
        return Line(mirror_point(shape.p1, line), mirror_point(shape.p2, line))
    if isinstance(shape, Circle):
        return Circle(mirror_point(shape.center, line), shape.radius.value)
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
