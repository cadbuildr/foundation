"""Compute functions for foundation schema directives."""

from typing import Any, Callable, Iterable, Optional, Sequence
import math
import re

from.gen.runtime import register_compute_fn, register_method_fn
from.gen.models import (
    Arc,
    Plane,
    Frame,
    StringParameter,
    BoolParameter,
    FloatParameter,
    Point,
    Sketch,
    Part,
    PartRoot,
    Assembly,
    AssemblyRoot,
)
from.helpers import PlaneFactory
from.constants import DEFAULT_COLORS, PLANES_CONFIG
from.math_utils import (
    quaternion_to_axes,
    axis_angle_to_quaternion,
    quaternion_multiply,
    create_frame_from_xdir_and_normal,
)


@register_compute_fn("get_plane_factory")
def get_plane_factory(inst: Any, field_name: str, meta: dict[str, Any]) -> PlaneFactory:
    """Get a PlaneFactory instance for creating derived planes."""
    return PlaneFactory()


@register_compute_fn("get_sketch_origin")
def get_sketch_origin(inst: Sketch, field_name: str, meta: dict[str, Any]) -> Point:
    """Get the origin point of a sketch from its plane."""
    return Point(sketch=inst, x=FloatParameter(value=0.0), y=FloatParameter(value=0.0))


@register_compute_fn("compute_convex_hull_lines")
def compute_convex_hull_lines(
    inst: Any, field_name: str, meta: dict[str, Any]
) -> list:
    """Compute the 2D convex hull of `inst.points` and return its boundary
    as a list of Lines (CCW). Falls back to a numpy-only Andrew monotone-chain
    algorithm so we don't take a hard dep on scipy.spatial.ConvexHull."""
    from.gen.models import Line

    pts = list(inst.points)
    if len(pts) < 3:
        raise ValueError("ConvexHull requires at least 3 points")
    sketch = pts[0].sketch
    coords = [(p.x.value, p.y.value) for p in pts]

    # Andrew monotone-chain convex hull (O(n log n)).
    coords_sorted = sorted(set(coords))
    if len(coords_sorted) < 3:
        raise ValueError("ConvexHull requires at least 3 distinct points")

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list = []
    for p in coords_sorted:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper: list = []
    for p in reversed(coords_sorted):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    hull = lower[:-1] + upper[:-1]

    def pt(x: float, y: float) -> Point:
        return Point(sketch=sketch, x=FloatParameter(value=x), y=FloatParameter(value=y))

    hull_pts = [pt(*c) for c in hull]
    return [Line(p1=hull_pts[i], p2=hull_pts[(i + 1) % len(hull_pts)]) for i in range(len(hull_pts))]


@register_compute_fn("compute_helix2d_points")
def compute_helix2d_points(
    inst: Any, field_name: str, meta: dict[str, Any]
) -> list:
    """Sample an Archimedean spiral r(θ) = pitch · θ / (2π) on [0, n_turns·2π].
    The spiral starts at (center.x, center.y) and grows outward to
    `radius_outer` at θ = n_turns·2π. Sampling density: ~32 points per turn,
    capped at 512 total."""
    cx = inst.center.x.value
    cy = inst.center.y.value
    sketch = inst.center.sketch
    pitch = inst.pitch.value
    radius_outer = inst.radius_outer.value
    n_turns = inst.n_turns.value

    if n_turns <= 0:
        raise ValueError("Helix2D.n_turns must be positive")
    expected_outer = pitch * n_turns
    if not math.isclose(expected_outer, radius_outer, rel_tol=1e-3):
        # Reconcile inputs by trusting `pitch` — this is the dimension users
        # most often parameterize from code.
        n_turns = radius_outer / pitch

    samples = min(512, max(32, int(32 * n_turns)))
    out: list = []
    for i in range(samples + 1):
        t = i / samples
        theta = t * n_turns * 2 * math.pi
        r = pitch * theta / (2 * math.pi)
        x = cx + r * math.cos(theta)
        y = cy + r * math.sin(theta)
        out.append(Point(sketch=sketch, x=FloatParameter(value=x), y=FloatParameter(value=y)))
    return out


@register_compute_fn("compute_sagitta_arc_control_point")
def compute_sagitta_arc_control_point(
    inst: Any, field_name: str, meta: dict[str, Any]
) -> Point:
    """Compute the arc-midpoint p2 for a SagittaArc(p1, p3, sagitta).

    The arc apex sits at signed distance `sagitta` from the chord midpoint
    along the chord-perpendicular (left of p1→p3 for positive sagitta)."""
    p1x, p1y = inst.p1.x.value, inst.p1.y.value
    p3x, p3y = inst.p3.x.value, inst.p3.y.value
    sketch = inst.p1.sketch
    sagitta = inst.sagitta.value

    mx, my = (p1x + p3x) / 2.0, (p1y + p3y) / 2.0
    dx, dy = p3x - p1x, p3y - p1y
    length = math.hypot(dx, dy)
    if length == 0:
        raise ValueError("SagittaArc requires distinct p1 and p3")
    # Left-of-chord perpendicular (rotate (dx, dy) 90° CCW).
    nx, ny = -dy / length, dx / length
    apex_x = mx + nx * sagitta
    apex_y = my + ny * sagitta
    return Point(sketch=sketch, x=FloatParameter(value=apex_x), y=FloatParameter(value=apex_y))


@register_compute_fn("compute_tangent_arc_control_point")
def compute_tangent_arc_control_point(
    inst: Any, field_name: str, meta: dict[str, Any]
) -> Point:
    """Mid-arc point p2 for TangentArc(p1, p3, tangent).

    Center O sits on the line through p1 perpendicular to `tangent`. With
    `n` = left-perp(tangent), the circle through p1 and p3 has signed
    radius r = (chord·chord) / (2·n·chord); O = p1 + r·n. The arc midpoint
    is found by sweeping from p1 around O by half the signed swept angle,
    where the sweep direction is fixed by which side of `tangent` the
    point p3 lies on (the tangent must point along the arc at p1)."""
    p1x, p1y = inst.p1.x.value, inst.p1.y.value
    p3x, p3y = inst.p3.x.value, inst.p3.y.value
    tx, ty = inst.tangent.x.value, inst.tangent.y.value
    sketch = inst.p1.sketch

    cx, cy = p3x - p1x, p3y - p1y
    chord_len_sq = cx * cx + cy * cy
    if chord_len_sq == 0:
        raise ValueError("TangentArc requires distinct p1 and p3")
    t_norm = math.hypot(tx, ty)
    if t_norm == 0:
        raise ValueError("TangentArc tangent vector must be non-zero")
    tx, ty = tx / t_norm, ty / t_norm
    nx, ny = -ty, tx  # Left-perp(tangent): rotate 90° CCW.
    n_dot_c = nx * cx + ny * cy
    if abs(n_dot_c) < 1e-12:
        # Tangent collinear with chord ⇒ degenerate arc; return chord midpoint.
        mx, my = (p1x + p3x) / 2.0, (p1y + p3y) / 2.0
        return Point(sketch=sketch, x=FloatParameter(value=mx), y=FloatParameter(value=my))
    r = chord_len_sq / (2.0 * n_dot_c)
    ox, oy = p1x + r * nx, p1y + r * ny
    abs_r = abs(r)
    # Sweep from p1 around O by half the swept angle.
    # CCW angle from p1 to p3 around O:
    a1x, a1y = p1x - ox, p1y - oy
    a3x, a3y = p3x - ox, p3y - oy
    cross = a1x * a3y - a1y * a3x
    dot = a1x * a3x + a1y * a3y
    full_angle = math.atan2(cross, dot)  # signed, in (-π, π]
    # Tangent at p1 going CCW around O is perpendicular to radius (a1x, a1y),
    # rotated 90° CCW: (-a1y, a1x). If given tangent agrees with this, sweep
    # CCW; otherwise sweep CW (through the long way around).
    ccw_tan_x, ccw_tan_y = -a1y, a1x
    if tx * ccw_tan_x + ty * ccw_tan_y < 0:
        # Sweep is CW; convert full_angle to the negative-direction sweep.
        if full_angle > 0:
            full_angle -= 2.0 * math.pi
        elif full_angle == 0:
            full_angle = -2.0 * math.pi
    else:
        if full_angle < 0:
            full_angle += 2.0 * math.pi
    half = full_angle / 2.0
    cos_h, sin_h = math.cos(half), math.sin(half)
    # Rotate (a1x, a1y) by `half` around origin, scale to abs_r.
    rx = cos_h * a1x - sin_h * a1y
    ry = sin_h * a1x + cos_h * a1y
    apex_x = ox + rx
    apex_y = oy + ry
    return Point(sketch=sketch, x=FloatParameter(value=apex_x), y=FloatParameter(value=apex_y))


@register_compute_fn("compute_jern_arc_endpoint")
def compute_jern_arc_endpoint(
    inst: Any, field_name: str, meta: dict[str, Any]
) -> Point:
    """End point p3 for JernArc(start, tangent, radius, arc_size_deg).

    Center is at start + radius · normal(tangent), where normal is the
    left-perpendicular to the tangent. End point is start rotated about
    the center by `arc_size_deg` (positive = CCW around the center)."""
    sx, sy = inst.start.x.value, inst.start.y.value
    tx, ty = inst.tangent.x.value, inst.tangent.y.value
    radius = inst.radius.value
    sweep_deg = inst.arc_size_deg.value
    sketch = inst.start.sketch

    t_norm = math.hypot(tx, ty)
    if t_norm == 0:
        raise ValueError("JernArc tangent vector must be non-zero")
    tx, ty = tx / t_norm, ty / t_norm
    # Left-perpendicular places the center on the CCW side of motion.
    nx, ny = -ty, tx
    ox, oy = sx + radius * nx, sy + radius * ny
    theta = math.radians(sweep_deg)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    rx, ry = sx - ox, sy - oy
    ex = ox + cos_t * rx - sin_t * ry
    ey = oy + sin_t * rx + cos_t * ry
    return Point(sketch=sketch, x=FloatParameter(value=ex), y=FloatParameter(value=ey))


@register_compute_fn("compute_jern_arc_midpoint")
def compute_jern_arc_midpoint(
    inst: Any, field_name: str, meta: dict[str, Any]
) -> Point:
    """Mid-arc point p2 for JernArc — start rotated by half the sweep."""
    sx, sy = inst.start.x.value, inst.start.y.value
    tx, ty = inst.tangent.x.value, inst.tangent.y.value
    radius = inst.radius.value
    sweep_deg = inst.arc_size_deg.value
    sketch = inst.start.sketch

    t_norm = math.hypot(tx, ty)
    tx, ty = tx / t_norm, ty / t_norm
    nx, ny = -ty, tx
    ox, oy = sx + radius * nx, sy + radius * ny
    theta = math.radians(sweep_deg / 2.0)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    rx, ry = sx - ox, sy - oy
    mx = ox + cos_t * rx - sin_t * ry
    my = oy + sin_t * rx + cos_t * ry
    return Point(sketch=sketch, x=FloatParameter(value=mx), y=FloatParameter(value=my))


@register_compute_fn("compute_polyline_primitives")
def compute_polyline_primitives(
    inst: Any, field_name: str, meta: dict[str, Any]
) -> list:
    """N-1 consecutive Lines through `inst.points`."""
    from.gen.models import Line

    pts = list(inst.points)
    if len(pts) < 2:
        raise ValueError("Polyline requires at least 2 points")
    return [Line(p1=pts[i], p2=pts[i + 1]) for i in range(len(pts) - 1)]


@register_compute_fn("compute_fillet_polyline_primitives")
def compute_fillet_polyline_primitives(
    inst: Any, field_name: str, meta: dict[str, Any]
) -> list:
    """Polyline with each interior vertex replaced by a tangent arc of
    `inst.radius`. Endpoints remain as-is. Each interior vertex contributes:
      - a Line from the previous tangent-out point to the new tangent-in
        point (cut short to leave room for the fillet);
      - an Arc with p2 at the arc midpoint on the inscribed circle."""
    from.gen.models import Line, Arc

    pts = list(inst.points)
    if len(pts) < 2:
        raise ValueError("FilletPolyline requires at least 2 points")
    radius = inst.radius.value
    if radius <= 0:
        raise ValueError("FilletPolyline.radius must be positive")
    sketch = pts[0].sketch

    coords = [(p.x.value, p.y.value) for p in pts]

    def pt(x: float, y: float) -> Point:
        return Point(sketch=sketch, x=FloatParameter(value=x), y=FloatParameter(value=y))

    def normalize(vx: float, vy: float) -> tuple[float, float]:
        mag = math.hypot(vx, vy)
        if mag == 0:
            return 0.0, 0.0
        return vx / mag, vy / mag

    if len(pts) == 2:
        return [Line(p1=pts[0], p2=pts[1])]

    primitives: list = []
    # Walk segments. For each interior vertex i (1..N-2), compute the
    # tangent points and arc midpoint, replacing the V_{i-1}→V_i→V_{i+1}
    # corner with: Line(prev_end → T_in_i), Arc(T_in_i → mid_i → T_out_i).
    # Endpoints are V_0 and V_{N-1}; the final closing line is
    # Line(T_out_{N-2} → V_{N-1}).
    prev_end = coords[0]
    for i in range(1, len(coords) - 1):
        a = coords[i - 1]
        b = coords[i]
        c = coords[i + 1]
        ux, uy = normalize(a[0] - b[0], a[1] - b[1])  # b → a
        vx, vy = normalize(c[0] - b[0], c[1] - b[1])  # b → c
        cos_2alpha = ux * vx + uy * vy
        # Clamp for numerical safety.
        cos_2alpha = max(-1.0, min(1.0, cos_2alpha))
        two_alpha = math.acos(cos_2alpha)
        alpha = two_alpha / 2.0
        if math.isclose(alpha, 0.0) or math.isclose(alpha, math.pi / 2):
            # Collinear or 180° turn — skip the fillet, treat as a straight pass.
            primitives.append(Line(p1=pt(*prev_end), p2=pt(*b)))
            prev_end = b
            continue
        tan_dist = radius / math.tan(alpha)
        # Defensive: if tan_dist exceeds the available segment length,
        # the corner can't be filleted at this radius.
        seg_in_len = math.hypot(b[0] - a[0], b[1] - a[1])
        seg_out_len = math.hypot(c[0] - b[0], c[1] - b[1])
        if tan_dist > seg_in_len or tan_dist > seg_out_len:
            raise ValueError(
                f"FilletPolyline: radius {radius} too large for vertex {i} — "
                f"requires {tan_dist:.3f} of segment length but adjacent "
                f"segments are {seg_in_len:.3f}, {seg_out_len:.3f}"
            )
        t_in = (b[0] + ux * tan_dist, b[1] + uy * tan_dist)
        t_out = (b[0] + vx * tan_dist, b[1] + vy * tan_dist)
        # Bisector pointing into the angle (toward arc center).
        bx, by = normalize(ux + vx, uy + vy)
        # Arc midpoint on the curve closest to V along the bisector.
        sin_alpha = math.sin(alpha)
        mid_offset = radius * (1.0 / sin_alpha - 1.0)
        mid = (b[0] + bx * mid_offset, b[1] + by * mid_offset)

        primitives.append(Line(p1=pt(*prev_end), p2=pt(*t_in)))
        primitives.append(Arc(p1=pt(*t_in), p2=pt(*mid), p3=pt(*t_out)))
        prev_end = t_out

    # Closing line to the last point.
    primitives.append(Line(p1=pt(*prev_end), p2=pt(*coords[-1])))
    return primitives


@register_compute_fn("compute_counterbore_profile_lines")
def compute_counterbore_profile_lines(
    inst: Any, field_name: str, meta: dict[str, Any]
) -> list:
    """L-shaped revolution profile for CounterBoreHole. Sketch coordinates:
    sketch X is the radial direction, sketch Y is the depth axis (0 = top
    surface, negative = into the material). Six corners CCW:
        (0,0) → (cbore_radius, 0) → (cbore_radius, -cbore_depth) →
        (radius, -cbore_depth) → (radius, -depth) → (0, -depth) → close to (0,0).
    """
    from.gen.models import Line

    cx = inst.point.x.value
    cy = inst.point.y.value
    sketch = inst.point.sketch
    rad = inst.radius.value
    depth = inst.depth.value
    cb_rad = inst.cbore_radius.value
    cb_depth = inst.cbore_depth.value

    if cb_radius_le_radius := (cb_rad <= rad):
        raise ValueError("CounterBoreHole.cbore_radius must exceed radius")
    if cb_depth >= depth:
        raise ValueError("CounterBoreHole.cbore_depth must be less than depth")

    def pt(x: float, y: float) -> Point:
        return Point(sketch=sketch, x=FloatParameter(value=x), y=FloatParameter(value=y))

    p0 = pt(cx, cy)
    p1 = pt(cx + cb_rad, cy)
    p2 = pt(cx + cb_rad, cy - cb_depth)
    p3 = pt(cx + rad, cy - cb_depth)
    p4 = pt(cx + rad, cy - depth)
    p5 = pt(cx, cy - depth)

    return [
        Line(p1=p0, p2=p1),
        Line(p1=p1, p2=p2),
        Line(p1=p2, p2=p3),
        Line(p1=p3, p2=p4),
        Line(p1=p4, p2=p5),
        Line(p1=p5, p2=p0),
    ]


@register_compute_fn("compute_countersink_profile_lines")
def compute_countersink_profile_lines(
    inst: Any, field_name: str, meta: dict[str, Any]
) -> list:
    """Stepped-chamfer profile for CounterSinkHole. Cone geometry:
    The countersink is a cone of half-angle `csink_angle_deg/2` blending
    from `csink_radius` at the top to `radius` at depth
    `cs_depth = (csink_radius - radius) / tan(half_angle)`. After the
    chamfer, a straight cylindrical section of radius `radius` continues
    down to total `depth`."""
    from.gen.models import Line

    cx = inst.point.x.value
    cy = inst.point.y.value
    sketch = inst.point.sketch
    rad = inst.radius.value
    depth = inst.depth.value
    cs_rad = inst.csink_radius.value
    angle_deg = inst.csink_angle_deg.value

    if cs_rad <= rad:
        raise ValueError("CounterSinkHole.csink_radius must exceed radius")
    if not (0 < angle_deg < 180):
        raise ValueError("CounterSinkHole.csink_angle_deg must be in (0, 180)")

    half_angle = math.radians(angle_deg) / 2.0
    cs_depth = (cs_rad - rad) / math.tan(half_angle)
    if cs_depth >= depth:
        raise ValueError(
            "Countersink chamfer depth exceeds total hole depth — "
            "increase `depth` or reduce `csink_radius`/cone-angle."
        )

    def pt(x: float, y: float) -> Point:
        return Point(sketch=sketch, x=FloatParameter(value=x), y=FloatParameter(value=y))

    p0 = pt(cx, cy)
    p1 = pt(cx + cs_rad, cy)
    p2 = pt(cx + rad, cy - cs_depth)  # bottom of chamfer (on inner radius)
    p3 = pt(cx + rad, cy - depth)
    p4 = pt(cx, cy - depth)

    return [
        Line(p1=p0, p2=p1),
        Line(p1=p1, p2=p2),
        Line(p1=p2, p2=p3),
        Line(p1=p3, p2=p4),
        Line(p1=p4, p2=p0),
    ]


@register_compute_fn("compute_slot_center_to_center_primitives")
def compute_slot_center_to_center_primitives(
    inst: Any, field_name: str, meta: dict[str, Any]
) -> list:
    """Build the 4 boundary primitives (2 lines + 2 semicircular arcs) of a
    SlotCenterToCenter from the centerline endpoints p1, p2 and slot width
    `height`."""
    from.gen.models import Line, Arc

    p1x, p1y = inst.p1.x.value, inst.p1.y.value
    p2x, p2y = inst.p2.x.value, inst.p2.y.value
    sketch = inst.p1.sketch
    r = inst.height.value / 2.0

    dx, dy = p2x - p1x, p2y - p1y
    length = math.hypot(dx, dy)
    if length == 0:
        raise ValueError("SlotCenterToCenter requires distinct p1 and p2")
    ux, uy = dx / length, dy / length
    # Perpendicular (rotate 90° CCW).
    nx, ny = -uy, ux

    def pt(x: float, y: float) -> Point:
        return Point(sketch=sketch, x=FloatParameter(value=x), y=FloatParameter(value=y))

    # Side line endpoints.
    a1 = pt(p1x + nx * r, p1y + ny * r)  # +offset at p1
    a2 = pt(p2x + nx * r, p2y + ny * r)  # +offset at p2
    b1 = pt(p2x - nx * r, p2y - ny * r)  # -offset at p2
    b2 = pt(p1x - nx * r, p1y - ny * r)  # -offset at p1

    # Semicircle midpoints (on the centerline ± direction).
    mid_p2 = pt(p2x + ux * r, p2y + uy * r)
    mid_p1 = pt(p1x - ux * r, p1y - uy * r)

    return [
        Line(p1=a1, p2=a2),
        Arc(p1=a2, p2=mid_p2, p3=b1),
        Line(p1=b1, p2=b2),
        Arc(p1=b2, p2=mid_p1, p3=a1),
    ]


@register_compute_fn("compute_rounded_rectangle_primitives")
def compute_rounded_rectangle_primitives(inst: Any, field_name: str, meta: dict[str, Any]) -> list:
    """Build the 8 boundary primitives (4 lines + 4 arcs) of a RectangleRounded.

    The rectangle is centered on `inst.center` with width `inst.w`, height
    `inst.h`, and corner fillet radius `inst.radius`. Each corner arc is a
    90° quarter-circle with `p2` placed at the arc midpoint (radius from the
    corner center, at 45°)."""
    from.gen.models import Line, Arc

    cx = inst.center.x.value
    cy = inst.center.y.value
    sketch = inst.center.sketch
    w = inst.w.value
    h = inst.h.value
    r = inst.radius.value

    if r <= 0:
        raise ValueError("RectangleRounded.radius must be positive")
    if r > min(w, h) / 2:
        raise ValueError(
            f"RectangleRounded.radius ({r}) cannot exceed min(w, h)/2 ({min(w, h) / 2})"
        )

    def pt(x: float, y: float) -> Point:
        return Point(sketch=sketch, x=FloatParameter(value=x), y=FloatParameter(value=y))

    inv_sqrt2 = math.sqrt(2) / 2

    # 8 line endpoints (corners of the rectangle minus the fillet bites).
    s_w = pt(cx - w / 2 + r, cy - h / 2)
    s_e = pt(cx + w / 2 - r, cy - h / 2)
    e_s = pt(cx + w / 2, cy - h / 2 + r)
    e_n = pt(cx + w / 2, cy + h / 2 - r)
    n_e = pt(cx + w / 2 - r, cy + h / 2)
    n_w = pt(cx - w / 2 + r, cy + h / 2)
    w_n = pt(cx - w / 2, cy + h / 2 - r)
    w_s = pt(cx - w / 2, cy - h / 2 + r)

    # Arc midpoints — corner center plus r*(±1/√2, ±1/√2).
    se_mid = pt(cx + w / 2 - r + r * inv_sqrt2, cy - h / 2 + r - r * inv_sqrt2)
    ne_mid = pt(cx + w / 2 - r + r * inv_sqrt2, cy + h / 2 - r + r * inv_sqrt2)
    nw_mid = pt(cx - w / 2 + r - r * inv_sqrt2, cy + h / 2 - r + r * inv_sqrt2)
    sw_mid = pt(cx - w / 2 + r - r * inv_sqrt2, cy - h / 2 + r - r * inv_sqrt2)

    return [
        Line(p1=s_w, p2=s_e),
        Arc(p1=s_e, p2=se_mid, p3=e_s),
        Line(p1=e_s, p2=e_n),
        Arc(p1=e_n, p2=ne_mid, p3=n_e),
        Line(p1=n_e, p2=n_w),
        Arc(p1=n_w, p2=nw_mid, p3=w_n),
        Line(p1=w_n, p2=w_s),
        Arc(p1=w_s, p2=sw_mid, p3=s_w),
    ]


@register_compute_fn("compute_arc_control_point")
def compute_arc_control_point(inst: Arc, field_name: str, meta: dict[str, Any]) -> Point:
    """Compute the control point (p2) for an arc from two points and radius.

    Based on old foundation implementation in arc.py:from_two_points_and_radius
    The arc is on the left side of the line from p1 to p2 when radius is positive.
    """
    p1 = inst.p1
    p2 = inst.p2
    radius_value = inst.radius.value
    sketch = inst.sketch

    # Calculate midpoint
    midpoint_x = (p1.x.value + p2.x.value) / 2
    midpoint_y = (p1.y.value + p2.y.value) / 2

    # Calculate distance between the points
    distance = math.sqrt(
        (p2.x.value - p1.x.value) ** 2 + (p2.y.value - p1.y.value) ** 2
    )

    if distance == 0:
        raise ValueError("The distance between the arc endpoints is zero")

    if distance > 2 * abs(radius_value):
        raise ValueError(
            f"The distance between points ({distance}) is greater than the diameter "
            f"of the circle (2 * {abs(radius_value)} = {2 * abs(radius_value)})"
        )

    # Calculate the direction perpendicular to the line segment
    dx = (p2.y.value - p1.y.value) / distance
    dy = -(p2.x.value - p1.x.value) / distance

    # Calculate offset from midpoint to control point
    # (p1, midpoint, center) forms a right triangle
    d = abs(radius_value) - math.sqrt(radius_value**2 - (distance / 2) ** 2)

    sign = math.copysign(1, radius_value)

    # Compute control point (on the arc, perpendicular to midpoint)
    control_x = midpoint_x - d * dx * sign
    control_y = midpoint_y - d * dy * sign

    return Point(
        sketch=sketch,
        x=FloatParameter(value=control_x),
        y=FloatParameter(value=control_y),
    )


@register_method_fn("add_element_method")
def add_element_method(inst: Sketch, element: Any) -> bool:
    """Add an element to the sketch's elements list."""
    # Initialize elements if it doesn't exist (though Pydantic should handle this)
    if not hasattr(inst, "elements") or inst.elements is None:
        inst.elements = []

    # Add element if not already present
    if element not in inst.elements:
        inst.elements.append(element)

    return True


@register_compute_fn("get_extrusion_sketch")
def get_extrusion_sketch(inst: Any, field_name: str, meta: dict[str, Any]) -> Sketch:
    """Get the sketch for an extrusion from its shape."""
    # The sketch is derived from the first shape's sketch attribute
    # shape is a list, so we get the first element
    if not inst.shape or len(inst.shape) == 0:
        raise ValueError("Extrusion must have at least one shape")

    first_shape = inst.shape[0]
    if hasattr(first_shape, "sketch"):
        sketch = first_shape.sketch
        # If sketch is None, try to compute it
        if sketch is None and hasattr(first_shape, "compute"):
            sketch = first_shape.compute("sketch")
        return sketch
    raise ValueError(f"Shape {first_shape} does not have a sketch attribute")


@register_compute_fn("compute_loft_sketches")
def compute_loft_sketches(
    inst: Any, field_name: str, meta: dict[str, Any]
) -> list[Sketch]:
    """Compute the list of sketches from the loft shapes."""
    sketches = []
    for shape in inst.shapes:
        if hasattr(shape, "sketch"):
            sketch = shape.sketch
            # If sketch is None, try to compute it
            if sketch is None and hasattr(shape, "compute"):
                sketch = shape.compute("sketch")
            if sketch is not None:
                sketches.append(sketch)
    return sketches


@register_compute_fn("compute_sheet_metal_base_sketch")
def compute_sheet_metal_base_sketch(
    inst: Any, field_name: str, meta: dict[str, Any]
) -> Sketch:
    """Compute the sketch used by a SheetMetalBaseFlange from its profile."""
    profile = inst.profile
    if hasattr(profile, "sketch"):
        sketch = profile.sketch
        if sketch is None and hasattr(profile, "compute"):
            sketch = profile.compute("sketch")
        if sketch is not None:
            return sketch
    raise ValueError(
        f"Profile {profile} does not provide a valid sketch for SheetMetalBaseFlange"
    )


@register_compute_fn("compute_sheet_metal_contour_sketch")
def compute_sheet_metal_contour_sketch(
    inst: Any, field_name: str, meta: dict[str, Any]
) -> Sketch:
    """Compute the sketch used by a SheetMetalContourFlange from its profile."""
    profile = inst.profile
    if hasattr(profile, "sketch"):
        sketch = profile.sketch
        if sketch is None and hasattr(profile, "compute"):
            sketch = profile.compute("sketch")
        if sketch is not None:
            return sketch
    raise ValueError(
        f"Profile {profile} does not provide a valid sketch for SheetMetalContourFlange"
    )


@register_compute_fn("compute_multi_section_sweep_sketches")
def compute_multi_section_sweep_sketches(
    inst: Any, field_name: str, meta: dict[str, Any]
) -> list[Sketch]:
    """Compute the list of sketches from the multi-section sweep profiles."""
    sketches = []
    for profile in inst.profiles:
        if hasattr(profile, "sketch"):
            sketch = profile.sketch
            if sketch is None and hasattr(profile, "compute"):
                sketch = profile.compute("sketch")
            if sketch is not None:
                sketches.append(sketch)
    return sketches


@register_compute_fn("compute_sweep_sketch")
def compute_sweep_sketch(inst: Any, field_name: str, meta: dict[str, Any]) -> Sketch:
    """Compute the sketch used by a sweep operation from its profile."""
    profile = inst.profile
    if hasattr(profile, "sketch"):
        sketch = profile.sketch
        if sketch is None and hasattr(profile, "compute"):
            sketch = profile.compute("sketch")
        if sketch is not None:
            return sketch
    raise ValueError(f"Profile {profile} does not provide a valid sketch for Sweep")


@register_compute_fn("compute_thread_path")
def compute_thread_path(inst: Any, field_name: str, meta: dict[str, Any]) -> Any:
    """Compute the helix path used by a thread macro node."""
    from.gen.models import Helix3D

    return Helix3D(
        pitch=inst.pitch,
        height=inst.height,
        radius=inst.radius,
        center=inst.center,
        dir=inst.dir,
        lefthand=inst.lefthand,
    )


def _create_plane_method(
    plane_name: str,
    config: tuple[list[int], list[int]] | None,
) -> Callable[[Any], Plane]:
    """Create a plane method function for a given plane name and configuration."""

    def plane_method(inst: Part) -> Plane:
        """Get a plane from a part's frame."""
        # Check if plane already exists in the planes list
        for existing_plane in inst.planes:
            plane_name_param = existing_plane.name
            if (
                hasattr(plane_name_param, "value")
                and plane_name_param.value == plane_name
            ):
                return existing_plane

        # Create new plane
        if config is None:
            # Special case: XY plane uses the part's frame directly
            plane = Plane(
                frame=inst.frame,
                name=StringParameter(value=plane_name),
                display=BoolParameter(value=False),
            )
        else:
            # Other planes: create frame with specific orientation
            x_dir, normal = config
            new_frame = create_frame_from_xdir_and_normal(
                inst.frame,
                x_dir,
                normal,
                f"{plane_name}_frame",  # Add "_frame" suffix to avoid name collision with plane
            )
            plane = Plane(
                frame=new_frame,
                name=StringParameter(value=plane_name),
                display=BoolParameter(value=False),
            )

        # Register the plane with the part
        inst.planes.append(plane)
        return plane

    # Set docstring
    plane_method.__doc__ = f"Get the {plane_name.upper()} plane from a part's frame."
    return plane_method


# Dynamically register all plane methods
for plane_name, config in PLANES_CONFIG.items():
    method_name = f"get_{plane_name}_plane"
    method_fn = _create_plane_method(plane_name, config)
    register_method_fn(method_name)(method_fn)


@register_method_fn("get_origin_planes_method")
def get_origin_planes_method(inst: Part | Assembly) -> list[Plane]:
    """Get the three main origin planes (xy, xz, yz) as a list."""
    return [inst.xy(), inst.xz(), inst.yz()]


@register_method_fn("add_operation_method")
def add_operation_method(inst: Part, operation: Any) -> bool:
    """Add an operation to a part."""
    from.gen.runtime import Expandable

    # If the operation is expandable (like Hole), expand it first
    if isinstance(operation, Expandable):
        operation = operation.expand()

    inst.operations.append(operation)
    return True


@register_method_fn("add_operations_method")
def add_operations_method(inst: Part, operations: Iterable[Any]) -> bool:
    """Add multiple operations to a part at once."""
    from.gen.runtime import Expandable

    for operation in operations:
        # If the operation is expandable (like Hole), expand it first
        if isinstance(operation, Expandable):
            operation = operation.expand()
        inst.operations.append(operation)
    return True


@register_method_fn("interface_grid_offset_method")
def interface_grid_offset_method(
    inst: Any, n_x: int = 0, n_y: int = 0, n_z: int = 0
) -> list[float]:
    """Compute a translation vector from integer grid offsets."""
    return [
        float(n_x) * float(inst.pitch_x.value),
        float(n_y) * float(inst.pitch_y.value),
        float(n_z) * float(inst.pitch_z.value),
    ]


@register_method_fn("interface_add_constraint_method")
def interface_add_constraint_method(
    inst: Any,
    component: Any,
    translation: Sequence[float],
    quaternion: Sequence[float] = (1.0, 0.0, 0.0, 0.0),
) -> bool:
    """Append a translation/quaternion-based placement constraint."""
    from.gen.models import FixedTranslationConstraint

    vector = _normalize_vector(translation, 3)
    quat = _normalize_vector(quaternion, 4)
    inst.constraints.append(
        FixedTranslationConstraint(component=component, translation=vector, quaternion=quat)
    )
    return True


@register_method_fn("interface_place_method")
def interface_place_method(
    inst: Any, component: Any, n_x: int = 0, n_y: int = 0, n_z: int = 0
) -> bool:
    """Place a component using this interface's grid spacing."""
    offset = inst.grid.offset(n_x=n_x, n_y=n_y, n_z=n_z)
    return inst.add_constraint(component=component, translation=offset)


@register_method_fn("interface_clip_method")
def interface_clip_method(
    inst: Any, component: Any, n_x: int = 0, n_y: int = 0, n_z: int = 1
) -> bool:
    """Convenience method to place one level above the current grid by default."""
    return interface_place_method(inst, component=component, n_x=n_x, n_y=n_y, n_z=n_z)


@register_method_fn("interface_apply_method")
def interface_apply_method(inst: Any, assembly: Any) -> bool:
    """Apply all stored constraints to the provided assembly."""
    for constraint in inst.constraints:
        assembly.add_component(
            constraint.component,
            tf={
                "translation": list(constraint.translation),
                "quaternion": list(constraint.quaternion),
            },
        )
    return True


# Counters for unique naming
_material_counter = 0


@register_method_fn("paint_method")
def paint_method(inst: Part | Assembly, color: str, transparency: float = 0.5) -> bool:
    """Paint a part (creates Material instance)."""
    global _material_counter
    from.gen.models import Material, MaterialOptions

    # Get RGB color from name
    if color not in DEFAULT_COLORS:
        raise ValueError(
            f"Unknown color '{color}'. Available colors: {list(DEFAULT_COLORS.keys())}"
        )

    diffuse_color = DEFAULT_COLORS[color]

    # Create Material instance
    _material_counter += 1
    material = Material(
        name=f"Material_{_material_counter}",
        painted_node_ids=[],
        options=MaterialOptions(diffuse_color=diffuse_color, transparency=float(transparency)),
    )

    # Store material on instance
    object.__setattr__(inst, "_material", material)
    return True


@register_method_fn("translate_method")
def translate_method(inst: Part | Assembly, translation: Sequence[float]) -> bool:
    """Translate a part or assembly by updating its frame position.

    For assemblies, only the assembly's frame is moved. Child components don't need
    updating because their frames are relative to the assembly frame.
    """
    if len(translation) != 3:
        raise ValueError("Translation vector must have exactly 3 components")
    vector = [float(translation[i]) for i in range(3)]
    inst.frame.position = [inst.frame.position[i] + vector[i] for i in range(3)]
    return True


@register_method_fn("translate_x_method")
def translate_x_method(inst: Part | Assembly, x: float) -> bool:
    """Translate a part or assembly along the X axis."""
    return translate_method(inst, [x, 0.0, 0.0])


@register_method_fn("translate_y_method")
def translate_y_method(inst: Part | Assembly, y: float) -> bool:
    """Translate a part or assembly along the Y axis."""
    return translate_method(inst, [0.0, y, 0.0])


@register_method_fn("translate_z_method")
def translate_z_method(inst: Part | Assembly, z: float) -> bool:
    """Translate a part or assembly along the Z axis."""
    return translate_method(inst, [0.0, 0.0, z])


@register_method_fn("rotate_method")
def rotate_method(inst: Part | Assembly, angle: float, axis: Sequence[float] = (0.0, 0.0, 1.0)) -> bool:
    """Rotate a part or assembly around an axis by updating its frame quaternion.

    Args:
        angle: Rotation angle in radians
        axis: Rotation axis (default: [0, 0, 1] for Z-axis rotation)
    """
    # Backward compatibility: allow rotate(axis, angle) call signature.
    if isinstance(axis, (int, float)) and hasattr(angle, "__len__"):
        angle, axis = axis, angle
    if len(axis) != 3:
        raise ValueError("Axis vector must have exactly 3 components")

    # Convert axis-angle to quaternion
    rotation_quat = axis_angle_to_quaternion(axis, angle)

    # Multiply: new_quat = rotation_quat * current_quat (apply rotation)
    inst.frame.quaternion = quaternion_multiply(rotation_quat, inst.frame.quaternion)

    # Note: For assemblies, we only rotate the assembly frame
    # Child components will follow since their frames reference the assembly frame
    return True


@register_method_fn("to_dag_method")
def to_dag_method(
    inst: Part | Assembly, memo: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Convert Part or Assembly to raw DAG dictionary (not formatted with version/rootNodeId)."""
    from.foundation_hooks import setup_foundation_hooks
    from.gen.dag import pydantic_to_dag
    from.constants import DEFAULT_TYPE_REGISTRY

    if memo is None:
        memo = {}

    hooks = setup_foundation_hooks()
    type_registry = DEFAULT_TYPE_REGISTRY.copy()

    # Convert to root if needed
    from.compute_functions import _convert_component_to_root

    if isinstance(inst, (Part, Assembly)):
        inst = _convert_component_to_root(inst)

    # Resolve slug-name collisions across the full tree before serializing.
    _finalize_root_names(inst)

    pydantic_to_dag(inst, memo, type_registry, hooks)

    # Return raw memo dictionary (like old foundation)
    return memo


def make_origin_frame_default_frame(
    frame: Frame, component_id: str, new_top_frame: Optional[Frame]
) -> None:
    """Update a component's origin frame to point to a parent frame.

    This mimics the old foundation's behavior where component frames are updated
    in place. Planes that reference this frame will automatically follow the updated hierarchy.

    CRITICAL: When a frame gets a new top_frame, its position must be reset to [0,0,0]
    because positions are RELATIVE to the parent frame. The frontend will add the parent's
    position, so keeping the absolute position would double the translation!

    Args:
        frame: The component's frame (typically named "origin") - updated in place
        component_id: Unique identifier for the component
        new_top_frame: The parent frame (assembly frame) to point to
    """
    from.gen.models import StringParameter

    # Update the frame's top_frame in place (like old foundation's change_top_frame)
    if new_top_frame is not None:
        frame.top_frame = new_top_frame

    # NOTE: We do NOT reset position here!
    # If the user called translate on the Part before add_component,
    # that position represents the Part's position RELATIVE to its parent.
    # The frame.position should be kept as-is.

    # Update frame name if it's still "origin"
    if frame.name.value == "origin":
        frame.name = StringParameter(value=f"{component_id}_origin")


def _format_component_path(path: tuple[int, ...]) -> str:
    if not path:
        return "root"
    return "_".join(str(i) for i in path)


# Marker for tree-tagging an auto-generated slug name on a converted root.
# Stored as a transient attribute via object.__setattr__ since PartRoot /
# AssemblyRoot do not declare extra="allow".
_AUTO_SLUG_ATTR = "_foundation_auto_slug"


def _camel_to_snake(name: str) -> str:
    """Convert a CamelCase / PascalCase identifier to snake_case.

    Example: ``TableLeg`` -> ``table_leg``, ``HTTPServer`` -> ``http_server``.
    """
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _user_class_slug(component: Any, base_class_names: tuple[str, ...]) -> Optional[str]:
    """Return a snake_case slug if the component's runtime class is a user
    subclass of ``Part`` / ``Assembly`` (not the base class itself).

    Used to give parts/assemblies readable tree names derived from the user's
    class name (e.g. ``class TableLeg(Part)`` -> ``table_leg``). Returns
    ``None`` for direct ``Part()`` / ``Assembly()`` usage so that the existing
    deterministic ``part_<path>`` / ``assy_<path>`` fallback is preserved.
    """
    cls_name = type(component).__name__
    if cls_name in base_class_names:
        return None
    slug = _camel_to_snake(cls_name)
    return slug or None


def _convert_component_to_root(
    component: Any,
    parent_frame: Optional[Frame] = None,
    component_path: tuple[int, ...] = (),
) -> Optional[PartRoot | AssemblyRoot]:
    """Convert Part/Assembly instances to their root representations.

    Args:
        component: Part or Assembly to convert
        parent_frame: Optional parent frame (assembly frame) that component frame should point to
    """
    from.gen.models import Frame, StringParameter, BoolParameter

    if isinstance(component, PartRoot):
        # Component is already a PartRoot, but we may need to update its frame's top_frame
        if parent_frame is not None and component.frame.top_frame != parent_frame:
            # Update the frame's top_frame to point to parent
            component.frame.top_frame = parent_frame
        return component
    if isinstance(component, AssemblyRoot):
        # Component is already an AssemblyRoot, recursively update its components
        if parent_frame is not None:
            # Update this assembly's frame's top_frame
            component.frame.top_frame = parent_frame
            # Recursively update nested components
            for idx, child in enumerate(component.components):
                _convert_component_to_root(
                    child,
                    parent_frame=component.frame,
                    component_path=component_path + (idx,),
                )
        return component
    if isinstance(component, Part):
        # Update the component's frame to point to parent_frame (like old foundation)
        # This is all we need - planes that reference component.frame will automatically follow
        component_id = f"component_{_format_component_path(component_path)}"
        make_origin_frame_default_frame(
            component.frame,
            component_id,
            parent_frame if parent_frame is not None else component.frame.top_frame,
        )

        # Generate deterministic name if still using default 'part0'.
        # This avoids process-global counter side effects in DAG hashing.
        # If the user subclassed Part (e.g. ``class TableLeg(Part)``), use the
        # snake_case class name as the slug so the assembly tree shows
        # ``table_leg`` instead of ``part_<idx>``. A later finalize pass adds
        # numeric suffixes only when slug names collide within an assembly.
        part_name = component.name
        auto_slug: Optional[str] = None
        if part_name.value == "part0":
            slug = _user_class_slug(component, ("Part",))
            if slug is not None:
                part_name = StringParameter(value=slug)
                auto_slug = slug
            else:
                part_name = StringParameter(
                    value=f"part_{_format_component_path(component_path)}"
                )

        part_root = PartRoot(
            frame=component.frame,  # Use the updated frame (updated in place)
            name=part_name,
            operations=component.operations,  # No need to update - frames reference component.frame which we just updated
            planes=component.planes,  # No need to update - frames reference component.frame which we just updated
            material=getattr(component, "_material", None),
        )
        if auto_slug is not None:
            object.__setattr__(part_root, _AUTO_SLUG_ATTR, auto_slug)
        return part_root
    if isinstance(component, Assembly):
        # Create assembly frame first
        original_frame = component.frame
        unique_frame_name = (
            f"assembly_{_format_component_path(component_path)}_frame"
        )

        # KEEP the assembly's position - it represents the transform applied to this assembly
        assembly_frame = Frame(
            top_frame=original_frame.top_frame
            if parent_frame is None
            else parent_frame,
            name=StringParameter(value=unique_frame_name),
            display=BoolParameter(value=original_frame.display.value),
            position=original_frame.position.copy()
            if isinstance(original_frame.position, list)
            else original_frame.position,
            quaternion=original_frame.quaternion.copy()
            if isinstance(original_frame.quaternion, list)
            else original_frame.quaternion,
        )

        # RECURSIVELY convert nested components, passing assembly frame so component frames can point to it
        converted_components = []
        for idx, c in enumerate(component.components):
            converted = _convert_component_to_root(
                c,
                parent_frame=assembly_frame,
                component_path=component_path + (idx,),
            )
            converted_components.append(converted)

        # Generate deterministic assembly name if still using default 'assembly0'.
        # As with Part, prefer a snake_case slug derived from a user subclass
        # name (e.g. ``class TableAssembly(Assembly)`` -> ``table_assembly``).
        assembly_name = component.name
        auto_assembly_slug: Optional[str] = None
        if assembly_name.value == "assembly0":
            slug = _user_class_slug(component, ("Assembly",))
            if slug is not None:
                assembly_name = StringParameter(value=slug)
                auto_assembly_slug = slug
            else:
                assembly_name = StringParameter(
                    value=f"assy_{_format_component_path(component_path)}"
                )

        assembly_root = AssemblyRoot(
            frame=assembly_frame,
            name=assembly_name,
            components=converted_components,
            material=getattr(component, "_material", None),
        )
        if auto_assembly_slug is not None:
            object.__setattr__(
                assembly_root, _AUTO_SLUG_ATTR, auto_assembly_slug
            )
        return assembly_root


def _finalize_root_names(root: Any) -> Any:
    """Add numeric suffixes to auto-generated slug names that collide.

    Walks an already-converted ``PartRoot`` / ``AssemblyRoot`` tree and, within
    each ``AssemblyRoot``'s direct children, groups roots that were tagged with
    a slug-derived auto-name (via :data:`_AUTO_SLUG_ATTR`). Children whose slug
    is unique within the assembly keep their bare slug name (e.g. ``table_top``);
    children that share a slug get a 1-based numeric suffix (e.g. ``table_leg_1``,
    ``table_leg_2``). User-set names and the deterministic ``part_<path>`` /
    ``assy_<path>`` fallbacks are left untouched.

    This is idempotent: once a root has been suffixed its auto-slug tag is
    cleared so a second pass is a no-op.
    """
    if isinstance(root, AssemblyRoot):
        groups: dict[str, list[Any]] = {}
        for child in root.components:
            slug = getattr(child, _AUTO_SLUG_ATTR, None)
            if slug:
                groups.setdefault(slug, []).append(child)
        for slug, group in groups.items():
            if len(group) > 1:
                for idx, child in enumerate(group, start=1):
                    child.name = StringParameter(value=f"{slug}_{idx}")
            for child in group:
                # Clear the tag so subsequent finalize passes are no-ops and
                # the slug doesn't leak through serialization.
                try:
                    object.__delattr__(child, _AUTO_SLUG_ATTR)
                except AttributeError:
                    pass
        for child in root.components:
            _finalize_root_names(child)
    return root


def _translate_component_root(component_root: Any, vector: Sequence[float]) -> None:
    """Apply translation to component roots recursively."""
    if isinstance(component_root, PartRoot):
        component_root.frame.position = [
            component_root.frame.position[i] + vector[i] for i in range(3)
        ]
        return
    if isinstance(component_root, AssemblyRoot):
        component_root.frame.position = [
            component_root.frame.position[i] + vector[i] for i in range(3)
        ]
        for child in component_root.components:
            _translate_component_root(child, vector)
        return
    raise TypeError(
        f"Unsupported component type '{type(component_root).__name__}' for translation"
    )


@register_method_fn("add_component_method")
def add_component_method(inst: Assembly, component: Any, tf: Any = None) -> bool:
    """Add a component (part or assembly) to an assembly."""
    # Pass the assembly's frame as parent so child frames become relative to it
    component_root = _convert_component_to_root(component, parent_frame=inst.frame)
    translation, quaternion = _parse_component_tf(tf)
    if translation is not None:
        _apply_translation_to_root(component_root, translation)
    if quaternion is not None:
        _apply_rotation_to_root(component_root, quaternion)
    inst.components.append(component_root)
    return True


def _apply_translation_to_root(component_root: Any, vector: Sequence[float]) -> None:
    component_root.frame.position = [
        component_root.frame.position[i] + vector[i] for i in range(3)
    ]


def _apply_rotation_to_root(component_root: Any, quaternion: Sequence[float]) -> None:
    component_root.frame.quaternion = quaternion_multiply(
        list(quaternion), component_root.frame.quaternion
    )


def _parse_component_tf(tf: Any) -> tuple[list[float] | None, list[float] | None]:
    if tf is None:
        return None, None
    if hasattr(tf, "get_tf") and callable(tf.get_tf):
        tf = tf.get_tf()
    if isinstance(tf, dict):
        translation = tf.get("translation") or tf.get("position")
        quaternion = tf.get("quaternion") or tf.get("rotation")
        return (
            _normalize_vector(translation, 3) if translation is not None else None,
            _normalize_vector(quaternion, 4) if quaternion is not None else None,
        )
    if isinstance(tf, (list, tuple)):
        if len(tf) == 3:
            return _normalize_vector(tf, 3), None
        matrix: list[list[float]] | None = None
        if len(tf) == 4 and all(isinstance(row, (list, tuple)) for row in tf):
            matrix = [list(row) for row in tf]
        elif len(tf) == 16:
            matrix = [list(tf[i * 4 : i * 4 + 4]) for i in range(4)]
        if matrix is not None:
            import numpy as np
            from.math_utils import rotation_matrix_to_quaternion

            rot_matrix = np.array([row[:3] for row in matrix[:3]], dtype=float)
            translation = [
                float(matrix[0][3]),
                float(matrix[1][3]),
                float(matrix[2][3]),
            ]
            quaternion = rotation_matrix_to_quaternion(rot_matrix)
            return translation, quaternion
    return None, None


def _normalize_vector(value: Any, expected_len: int) -> list[float]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)):
        raise TypeError("Transform values must be a list-like sequence")
    values = [float(item) for item in value]
    if len(values) != expected_len:
        raise ValueError(f"Expected {expected_len} values, got {len(values)}")
    return values


@register_method_fn("get_parallel_plane_method")
def get_parallel_plane_method(inst: Plane, distance: float, name: str = "parallel") -> Plane:
    """Create a plane parallel to this plane at given distance."""
    # Get normal vector from frame's Z-axis (quaternion's up direction)
    # Quaternion format: [w, x, y, z]
    q = inst.frame.quaternion
    w, x, y, z = q[0], q[1], q[2], q[3]

    # Convert quaternion to rotation matrix and extract Z-axis (normal)
    # Z-axis is the third column of the rotation matrix
    normal_x = 2 * (x * z + w * y)
    normal_y = 2 * (y * z - w * x)
    normal_z = 1 - 2 * (x * x + y * y)

    # Translate frame position along the normal
    new_position = [
        inst.frame.position[0] + normal_x * distance,
        inst.frame.position[1] + normal_y * distance,
        inst.frame.position[2] + normal_z * distance,
    ]

    return Plane(
        frame=Frame(
            top_frame=inst.frame,
            name=StringParameter(value=f"frame_{name}"),
            display=BoolParameter(value=False),
            position=new_position,
            quaternion=inst.frame.quaternion,  # Same orientation
        ),
        name=StringParameter(value=name),
        display=BoolParameter(value=False),
    )


@register_method_fn("get_plane_x_axis")
def get_plane_x_axis(inst: Plane) -> list[float]:
    """Get the X-axis of the plane's frame."""
    x_axis, _, _ = quaternion_to_axes(inst.frame.quaternion)
    return x_axis


@register_method_fn("get_plane_y_axis")
def get_plane_y_axis(inst: Plane) -> list[float]:
    """Get the Y-axis of the plane's frame."""
    _, y_axis, _ = quaternion_to_axes(inst.frame.quaternion)
    return y_axis


@register_method_fn("get_plane_z_axis")
def get_plane_z_axis(inst: Plane) -> list[float]:
    """Get the Z-axis of the plane's frame."""
    _, _, z_axis = quaternion_to_axes(inst.frame.quaternion)
    return z_axis


@register_method_fn("get_angle_plane_from_axis_method")
def get_angle_plane_from_axis_method(
    inst: Plane, axis: Sequence[float], angle: float, name: str = "rotated"
) -> Plane:
    """Create a plane rotated around the given axis by the given angle."""
    # Convert axis-angle to quaternion
    rotation_quat = axis_angle_to_quaternion(axis, angle)

    # Multiply quaternions: new_quat = rotation_quat * original_quat
    new_quaternion = quaternion_multiply(rotation_quat, inst.frame.quaternion)

    return Plane(
        frame=Frame(
            top_frame=inst.frame,
            name=StringParameter(value=f"frame_{name}"),
            display=BoolParameter(value=False),
            position=[
                0.0,
                0.0,
                0.0,
            ],  # No translation, just rotation (position is relative to parent)
            quaternion=new_quaternion,  # New orientation
        ),
        name=StringParameter(value=name),
        display=BoolParameter(value=False),  # Don't display construction planes
    )
