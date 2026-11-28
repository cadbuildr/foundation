"""Sketch constraint solver (optional intent on explicit geometry).

When a sketch has constraints (``sketch.constrain(...)``), serializing it runs
``solve_sketch_constraints``: the points (and circle radii) the constraints
mention are moved, from where they were drawn, until every constraint holds.
The solved values replace those points' parameters, so kernels see plain
geometry. A sketch without constraints is never touched.

The algorithm is deliberately small and deterministic, and is mirrored step for
step in TS (foundation-runtime-schema/src/runtime/sketchSolver.ts) so the
viewer and Python land on the same coordinates:

* variables: x / y of every point and the radius of every circle in the
  sketch (its elements, in order; then anything the constraints mention that
  is not an element), start values the current ones; geometry no constraint
  touches has a zero gradient, so it does not move, but it counts for the
  degrees of freedom;
* residuals: one or two per constraint (``RESIDUALS``);
* damped, least-norm Gauss-Newton: dx = J^T (J J^T + mu I)^-1 (-r), halving
  the step while it does not reduce |r|; numerical Jacobian (central
  differences); stop when |r| < 1e-10 or after 100 iterations;
* status: ``"ok"`` (fully constrained), ``"under:<dof>"``, or ``"conflict"``
  (the constraints cannot all hold); degrees of freedom are
  ``variables - rank(J)`` at the solution.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Sequence, Tuple

TOL = 1e-10
MAX_ITER = 100
RANK_TOL = 1e-8
MU = 1e-12


class _Vars:
    """Solver variables: (object, attribute) pairs bound to current values."""

    def __init__(self) -> None:
        self.keys: List[Tuple[int, str]] = []
        self.owners: List[Tuple[Any, str]] = []
        self.index: Dict[Tuple[int, str], int] = {}
        self.x: List[float] = []

    def var(self, obj: Any, attr: str) -> int:
        key = (id(obj), attr)
        if key not in self.index:
            self.index[key] = len(self.x)
            self.keys.append(key)
            self.owners.append((obj, attr))
            self.x.append(float(getattr(obj, attr).value))
        return self.index[key]

    def point(self, p: Any) -> Tuple[int, int]:
        return self.var(p, "x"), self.var(p, "y")


def _line(v: _Vars, line: Any) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    return v.point(line.p1), v.point(line.p2)


# Each entry: constraint type → (collect variables, residuals(x) → list[float]).
def _residual_fns(v: _Vars, c: Any) -> Callable[[List[float]], List[float]]:
    t = type(c).__name__
    if t == "Coincident":
        a, b = v.point(c.p1), v.point(c.p2)
        return lambda x: [x[a[0]] - x[b[0]], x[a[1]] - x[b[1]]]
    if t == "PointOnLine":
        p = v.point(c.point)
        a, b = _line(v, c.line)

        def r(x):
            dx, dy = x[b[0]] - x[a[0]], x[b[1]] - x[a[1]]
            n = math.hypot(dx, dy) or 1.0
            return [((x[p[0]] - x[a[0]]) * dy - (x[p[1]] - x[a[1]]) * dx) / n]

        return r
    if t == "Horizontal":
        a, b = _line(v, c.line)
        return lambda x: [x[b[1]] - x[a[1]]]
    if t == "Vertical":
        a, b = _line(v, c.line)
        return lambda x: [x[b[0]] - x[a[0]]]
    if t in ("Parallel", "Perpendicular", "Equal", "Angle"):
        a1, b1 = _line(v, c.line1)
        a2, b2 = _line(v, c.line2)
        target = math.radians(c.value.value) if t == "Angle" else 0.0

        def r(x):
            d1 = (x[b1[0]] - x[a1[0]], x[b1[1]] - x[a1[1]])
            d2 = (x[b2[0]] - x[a2[0]], x[b2[1]] - x[a2[1]])
            n1 = math.hypot(*d1) or 1.0
            n2 = math.hypot(*d2) or 1.0
            cross = (d1[0] * d2[1] - d1[1] * d2[0]) / (n1 * n2)
            dot = (d1[0] * d2[0] + d1[1] * d2[1]) / (n1 * n2)
            if t == "Parallel":
                return [cross]
            if t == "Perpendicular":
                return [dot]
            if t == "Equal":
                return [n1 - n2]
            return [math.atan2(cross, dot) - target]

        return r
    if t == "Tangent":
        a, b = _line(v, c.line)
        ctr = v.point(c.circle.center)
        rad = v.var(c.circle, "radius")

        def r(x):
            dx, dy = x[b[0]] - x[a[0]], x[b[1]] - x[a[1]]
            n = math.hypot(dx, dy) or 1.0
            dist = abs((x[ctr[0]] - x[a[0]]) * dy - (x[ctr[1]] - x[a[1]]) * dx) / n
            return [dist - x[rad]]

        return r
    if t == "Concentric":
        a, b = v.point(c.circle1.center), v.point(c.circle2.center)
        return lambda x: [x[a[0]] - x[b[0]], x[a[1]] - x[b[1]]]
    if t == "Fix":
        p = v.point(c.point)
        x0, y0 = v.x[p[0]], v.x[p[1]]
        return lambda x: [x[p[0]] - x0, x[p[1]] - y0]
    if t in ("Distance", "HorizontalDistance", "VerticalDistance"):
        a, b = v.point(c.p1), v.point(c.p2)
        d = float(c.value.value)
        if t == "Distance":
            return lambda x: [math.hypot(x[b[0]] - x[a[0]], x[b[1]] - x[a[1]]) - d]
        if t == "HorizontalDistance":
            return lambda x: [(x[b[0]] - x[a[0]]) - d]
        return lambda x: [(x[b[1]] - x[a[1]]) - d]
    if t in ("Radius", "Diameter"):
        rad = v.var(c.circle, "radius")
        d = float(c.value.value)
        return (lambda x: [x[rad] - d]) if t == "Radius" else (lambda x: [2 * x[rad] - d])
    raise ValueError(f"sketch solver: unknown constraint {t}")


def _solve_linear(a: List[List[float]], b: List[float]) -> List[float]:
    """Gaussian elimination with partial pivoting (a is square)."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-300:
            continue
        m[col], m[piv] = m[piv], m[col]
        for r in range(col + 1, n):
            f = m[r][col] / m[col][col]
            if f:
                for k in range(col, n + 1):
                    m[r][k] -= f * m[col][k]
    out = [0.0] * n
    for r in range(n - 1, -1, -1):
        s = m[r][n] - sum(m[r][k] * out[k] for k in range(r + 1, n))
        out[r] = s / m[r][r] if abs(m[r][r]) > 1e-300 else 0.0
    return out


def _rank(rows: List[List[float]]) -> int:
    m = [r[:] for r in rows]
    if not m:
        return 0
    n_cols = len(m[0])
    rank = 0
    for col in range(n_cols):
        piv = max(range(rank, len(m)), key=lambda r: abs(m[r][col]), default=None)
        if piv is None or abs(m[piv][col]) < RANK_TOL:
            continue
        m[rank], m[piv] = m[piv], m[rank]
        for r in range(len(m)):
            if r != rank and m[r][col]:
                f = m[r][col] / m[rank][col]
                for k in range(col, n_cols):
                    m[r][k] -= f * m[rank][k]
        rank += 1
        if rank == len(m):
            break
    return rank


def _register_elements(v: _Vars, elements: Sequence[Any]) -> None:
    for el in elements:
        t = type(el).__name__
        if t == "Point":
            v.point(el)
        elif t == "Circle":
            v.point(el.center)
            v.var(el, "radius")


def solve(
    constraints: Sequence[Any], elements: Sequence[Any] = (), fixed: Sequence[Any] = ()
) -> Tuple[_Vars, List[float], str]:
    """Solve; returns the variables, their solved values and the status.

    ``fixed`` points (the sketch origin) never move: when the solve uses them,
    they are held where they are, like a ``Fix``.
    """
    v = _Vars()
    _register_elements(v, elements)
    fns = [_residual_fns(v, c) for c in constraints]
    for p in fixed:
        if p is not None and (id(p), "x") in v.index:
            a = v.point(p)
            fns.append(lambda x, a=a, x0=v.x[a[0]], y0=v.x[a[1]]: [x[a[0]] - x0, x[a[1]] - y0])

    def residual(x: List[float]) -> List[float]:
        out: List[float] = []
        for f in fns:
            out.extend(f(x))
        return out

    def jacobian(x: List[float]) -> List[List[float]]:
        cols = []
        for i in range(len(x)):
            h = 1e-7 * max(1.0, abs(x[i]))
            xp = x[:]
            xm = x[:]
            xp[i] += h
            xm[i] -= h
            rp, rm = residual(xp), residual(xm)
            cols.append([(rp[k] - rm[k]) / (2 * h) for k in range(len(rp))])
        return [[cols[j][k] for j in range(len(x))] for k in range(len(cols[0]) if cols else 0)]

    x = v.x[:]
    r = residual(x)
    norm = math.sqrt(sum(e * e for e in r))
    for _ in range(MAX_ITER):
        if norm < TOL or not x:
            break
        j = jacobian(x)
        jjt = [[sum(j[a][k] * j[b][k] for k in range(len(x))) + (MU if a == b else 0.0) for b in range(len(j))] for a in range(len(j))]
        y = _solve_linear(jjt, [-e for e in r])
        dx = [sum(j[k][i] * y[k] for k in range(len(j))) for i in range(len(x))]
        step = 1.0
        for _half in range(20):
            xn = [x[i] + step * dx[i] for i in range(len(x))]
            rn = residual(xn)
            nn = math.sqrt(sum(e * e for e in rn))
            if nn < norm:
                break
            step /= 2
        else:
            break
        x, r, norm = xn, rn, nn

    if norm >= 1e-6:
        return v, x, "conflict"
    dof = len(x) - _rank(jacobian(x)) if x else 0
    return v, x, "ok" if dof == 0 else f"under:{dof}"


def solve_sketch(sketch: Any) -> str | None:
    """Solve a sketch's constraints in place; None when it has none."""
    constraints = getattr(sketch, "constraints", None)
    if not constraints:
        return None
    from .gen.models import FloatParameter

    v, x, status = solve(constraints, list(sketch.elements or []), fixed=[getattr(sketch, "origin", None)])
    # Only what moved; new parameter objects, never mutate: a FloatParameter may
    # be shared with other features (a WIDTH used by an extrusion too).
    for (obj, attr), start, value in zip(v.owners, v.x, x):
        if value != start:
            setattr(obj, attr, FloatParameter(value=value))
    return status
