"""Compute functions for foundation schema directives."""

from typing import Any, Callable, Iterable, Optional, Sequence
import math
import re

from .gen.runtime import register_compute_fn, register_method_fn
from .gen.runtime.helpers import register_cast_fn


@register_cast_fn("cast_edge_ref")
def _cast_edge_ref(v):
    """Route a bare value passed for an EdgeRef field: an EdgeFinder becomes a
    query reference, anything else (a Line) becomes a constructed reference."""
    from .gen.models import EdgeFinder, Line

    if isinstance(v, EdgeFinder):
        return {"finder": v}
    if isinstance(v, Line):
        return {"line": v}
    # A sheet-metal operation stands for the FREE edge of the flange it created.
    return {"flange": v}


from .gen.models import (
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
from .helpers import PlaneFactory
from .constants import ColorSpec, PLANES_CONFIG, resolve_color
from .math_utils import (
    quaternion_to_axes,
    axis_angle_to_quaternion,
    quaternion_multiply,
    create_frame_from_xdir_and_normal,
    compose_tf,
    invert_tf,
    link_frame_aliases,
    tf_relative_to_frame,
)
from .placement import (
    DEFAULT_ANGLE_TOL_DEG,
    DEFAULT_POS_TOL,
    check_loop_closure,
    rotation_from_deg,
)


@register_compute_fn("solve_sketch_constraints")
def solve_sketch_constraints(
    inst: Sketch, field_name: str, meta: dict[str, Any]
) -> str | None:
    """Solve a sketch's optional constraints (see sketch_solver); None when it has none."""
    from .sketch_solver import solve_sketch

    return solve_sketch(inst)


@register_method_fn("constrain_method")
def constrain_method(inst: Sketch, constraints: Any) -> bool:
    """Add constraints / dimensions to a sketch: ``sketch.constrain([Horizontal(l1), Distance(a, b, 60)])``."""
    items = (
        list(constraints) if isinstance(constraints, (list, tuple)) else [constraints]
    )
    if inst.constraints is None:
        inst.constraints = []
    inst.constraints.extend(items)
    # Solve again at the next serialization.
    object.__setattr__(inst, "solve_status", None)
    return True


@register_compute_fn("get_plane_factory")
def get_plane_factory(inst: Any, field_name: str, meta: dict[str, Any]) -> PlaneFactory:
    """Get a PlaneFactory instance for creating derived planes."""
    return PlaneFactory()


@register_compute_fn("get_sketch_origin")
def get_sketch_origin(inst: Sketch, field_name: str, meta: dict[str, Any]) -> Point:
    """Get the origin point of a sketch from its plane."""
    return Point(sketch=inst, x=FloatParameter(value=0.0), y=FloatParameter(value=0.0))


@register_compute_fn("compute_convex_hull_lines")
def compute_convex_hull_lines(inst: Any, field_name: str, meta: dict[str, Any]) -> list:
    """Compute the 2D convex hull of `inst.points` and return its boundary
    as a list of Lines (CCW). Falls back to a numpy-only Andrew monotone-chain
    algorithm so we don't take a hard dep on scipy.spatial.ConvexHull."""
    from .gen.models import Line

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
        return Point(
            sketch=sketch, x=FloatParameter(value=x), y=FloatParameter(value=y)
        )

    hull_pts = [pt(*c) for c in hull]
    return [
        Line(p1=hull_pts[i], p2=hull_pts[(i + 1) % len(hull_pts)])
        for i in range(len(hull_pts))
    ]


@register_compute_fn("compute_helix2d_points")
def compute_helix2d_points(inst: Any, field_name: str, meta: dict[str, Any]) -> list:
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
        out.append(
            Point(sketch=sketch, x=FloatParameter(value=x), y=FloatParameter(value=y))
        )
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
    return Point(
        sketch=sketch, x=FloatParameter(value=apex_x), y=FloatParameter(value=apex_y)
    )


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
        return Point(
            sketch=sketch, x=FloatParameter(value=mx), y=FloatParameter(value=my)
        )
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
    return Point(
        sketch=sketch, x=FloatParameter(value=apex_x), y=FloatParameter(value=apex_y)
    )


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
    from .gen.models import Line

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
    from .gen.models import Line, Arc

    pts = list(inst.points)
    if len(pts) < 2:
        raise ValueError("FilletPolyline requires at least 2 points")
    radius = inst.radius.value
    if radius <= 0:
        raise ValueError("FilletPolyline.radius must be positive")
    sketch = pts[0].sketch

    coords = [(p.x.value, p.y.value) for p in pts]

    def pt(x: float, y: float) -> Point:
        return Point(
            sketch=sketch, x=FloatParameter(value=x), y=FloatParameter(value=y)
        )

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


def _hole_revolve_sketch(point: Point) -> Sketch:
    """Return a Sketch on a plane through ``point`` that is perpendicular to the
    hole's host sketch, oriented so the new sketch's local **Y axis maps to the
    host sketch normal** (the bore axis).

    Counterbore / countersink profiles are revolved with a ``Lathe`` about the
    new sketch's Y axis. Drawing the profile here — radial along local X, axial
    along local Y — means the revolution axis coincides with the host normal, so
    the bore is drilled *into the face* (along the normal), exactly like the
    plain :class:`Hole` (which extrudes a circle along the normal). This is the
    same trick the ``Torus`` docs describe: put the profile on a sketch whose Y
    maps to the desired world revolution axis.

    The host frame is rotated +90° about its local X axis (so local Y → host
    normal, local Z → −host Y) and translated to the hole point, so a profile
    point ``(u, v)`` lands at ``host_point + u·host_X + v·host_normal``.
    """
    host_frame = point.sketch.plane.frame
    rot_quat = axis_angle_to_quaternion([1.0, 0.0, 0.0], math.pi / 2.0)
    frame = Frame(
        top_frame=host_frame,
        name=StringParameter(value="hole_revolve_frame"),
        display=BoolParameter(value=False),
        position=[point.x.value, point.y.value, 0.0],
        quaternion=rot_quat,
    )
    plane = Plane(
        frame=frame,
        name=StringParameter(value="hole_revolve"),
        display=BoolParameter(value=False),
    )
    return Sketch(plane=plane)


@register_compute_fn("compute_hole_axis_line")
def compute_hole_axis_line(inst: Any, field_name: str, meta: dict[str, Any]) -> Any:
    """Revolution axis for CounterBoreHole / CounterSinkHole.

    The axis is the local-Y line of the perpendicular revolve sketch (see
    :func:`_hole_revolve_sketch`), which maps to the host sketch normal — so the
    bore is drilled along the face normal, matching the plain ``Hole``."""
    from .gen.models import Line

    sketch = _hole_revolve_sketch(inst.point)
    return Line(
        p1=Point(
            sketch=sketch, x=FloatParameter(value=0.0), y=FloatParameter(value=-1.0)
        ),
        p2=Point(
            sketch=sketch, x=FloatParameter(value=0.0), y=FloatParameter(value=1.0)
        ),
    )


@register_compute_fn("compute_counterbore_profile_lines")
def compute_counterbore_profile_lines(
    inst: Any, field_name: str, meta: dict[str, Any]
) -> list:
    """L-shaped revolution profile for CounterBoreHole, drawn on the
    perpendicular revolve sketch (local X = radial, local Y = depth along the
    host face normal; 0 = entry surface, increasing = into the material). Six
    corners CCW:
        (0,0) → (cbore_radius,0) → (cbore_radius,cbore_depth) →
        (radius,cbore_depth) → (radius,depth) → (0,depth) → close to (0,0).
    The wide counterbore step sits at the entry surface (depth 0); the narrow
    bore continues to ``depth``.
    """
    from .gen.models import Line

    sketch = _hole_revolve_sketch(inst.point)
    rad = inst.radius.value
    depth = inst.depth.value
    cb_rad = inst.cbore_radius.value
    cb_depth = inst.cbore_depth.value

    if cb_rad <= rad:
        raise ValueError("CounterBoreHole.cbore_radius must exceed radius")
    if cb_depth >= depth:
        raise ValueError("CounterBoreHole.cbore_depth must be less than depth")

    def pt(x: float, y: float) -> Point:
        return Point(
            sketch=sketch, x=FloatParameter(value=x), y=FloatParameter(value=y)
        )

    p0 = pt(0.0, 0.0)
    p1 = pt(cb_rad, 0.0)
    p2 = pt(cb_rad, cb_depth)
    p3 = pt(rad, cb_depth)
    p4 = pt(rad, depth)
    p5 = pt(0.0, depth)

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
    """Stepped-chamfer profile for CounterSinkHole, drawn on the perpendicular
    revolve sketch (local X = radial, local Y = depth along the host face
    normal; 0 = entry surface, increasing = into the material).

    The countersink is a cone of half-angle `csink_angle_deg/2` blending from
    `csink_radius` at the entry surface to `radius` at depth
    `cs_depth = (csink_radius - radius) / tan(half_angle)`. After the chamfer, a
    straight cylindrical section of radius `radius` continues to total `depth`.
    """
    from .gen.models import Line

    sketch = _hole_revolve_sketch(inst.point)
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
        return Point(
            sketch=sketch, x=FloatParameter(value=x), y=FloatParameter(value=y)
        )

    p0 = pt(0.0, 0.0)
    p1 = pt(cs_rad, 0.0)
    p2 = pt(rad, cs_depth)  # bottom of chamfer (on inner radius)
    p3 = pt(rad, depth)
    p4 = pt(0.0, depth)

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
    from .gen.models import Line, Arc

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
        return Point(
            sketch=sketch, x=FloatParameter(value=x), y=FloatParameter(value=y)
        )

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
def compute_rounded_rectangle_primitives(
    inst: Any, field_name: str, meta: dict[str, Any]
) -> list:
    """Build the 8 boundary primitives (4 lines + 4 arcs) of a RectangleRounded.

    The rectangle is centered on `inst.center` with width `inst.w`, height
    `inst.h`, and corner fillet radius `inst.radius`. Each corner arc is a
    90° quarter-circle with `p2` placed at the arc midpoint (radius from the
    corner center, at 45°)."""
    from .gen.models import Line, Arc

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
        return Point(
            sketch=sketch, x=FloatParameter(value=x), y=FloatParameter(value=y)
        )

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
def compute_arc_control_point(
    inst: Arc, field_name: str, meta: dict[str, Any]
) -> Point:
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
    from .gen.models import Helix3D

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


def _fully_expand_operation(operation: Any) -> Any:
    """Expand an operation transitively until it reaches a non-expandable node.

    Expansion is one level per ``expand()`` call, but some sugar nodes expand
    into other sugar nodes (e.g. ``TappedHole`` -> ``Hole`` -> ``Extrusion``).
    A single expand would leave a ``Hole`` node in the operations list; because
    ``Hole`` is a registered (valid) type, the DAG serializer would not expand
    it either, and the kernel — which has no real ``Hole`` handler — fails to
    build the geometry. Loop until the result is no longer expandable.
    """
    from .gen.runtime import Expandable

    # Guard against a pathological expand() that never reaches a terminal node.
    for _ in range(100):
        if not isinstance(operation, Expandable):
            return operation
        operation = operation.expand()
    raise ValueError(
        f"Operation {type(operation).__name__} did not reduce to a "
        f"non-expandable node after 100 expansions; possible expansion cycle."
    )


@register_method_fn("add_operation_method")
def add_operation_method(inst: Part, operation: Any) -> bool:
    """Add an operation to a part."""
    # If the operation is expandable (like Hole), expand it first.
    operation = _fully_expand_operation(operation)

    inst.operations.append(operation)
    return True


@register_method_fn("add_operations_method")
def add_operations_method(inst: Part, operations: Iterable[Any]) -> bool:
    """Add multiple operations to a part at once."""
    for operation in operations:
        # If the operation is expandable (like Hole), expand it first.
        operation = _fully_expand_operation(operation)
        inst.operations.append(operation)
    return True


# --------------------------------------------------------------------------- #
# Anchors ("mate connectors"): named frames on a Part/Assembly. Convention:
# +Z is the mate axis / outward normal, +X the clocking direction.
# The anchor -> owner back-reference is a transient attribute (never a model
# field) so the serialized DAG stays acyclic.
# --------------------------------------------------------------------------- #

_ANCHOR_OWNER_ATTR = "_anchor_owner"


def _anchor_owner(anchor: Any) -> Any:
    owner = getattr(anchor, _ANCHOR_OWNER_ATTR, None)
    if owner is None:
        raise ValueError(
            f"Anchor '{anchor.name.value}' has no owner. Attach it with "
            "part.add_anchor(anchor) (or assembly.add_anchor) before using it "
            "in a joint."
        )
    return owner


def _set_anchor_owner(anchor: Any, owner: Any) -> None:
    object.__setattr__(anchor, _ANCHOR_OWNER_ATTR, owner)


# --------------------------------------------------------------------------- #
# Anchor naming. One rule, two cases:
#   * a name the caller REGISTERS (part.add_anchor) is a lookup key
#     (part.anchor("top"), downstream libraries) -> a duplicate RAISES;
#     silently renaming it would make lookups order-dependent.
#   * a DERIVED anchor's name (offset/rotated/flipped/patterns) is generated
#     as "<base>_<label>" and is unique by construction: if that name is
#     already used in the owner's namespace it gets "_2", "_3", ... Callers
#     hold the returned object, never look it up by name, so no counters are
#     needed (woodworking's global _seq(), the tube-tee "tee_seat" clash).
# The namespace is the owner's registered anchors plus every name derived
# from its anchors (transient attribute, never serialised). Anchors derived
# from an unowned anchor share that root anchor's namespace, merged into the
# owner's when the root is registered.
# --------------------------------------------------------------------------- #

_DERIVED_NAMES_ATTR = "_derived_anchor_names"
_NAMESPACE_ROOT_ATTR = "_anchor_namespace_root"
_RESERVED_IN_ATTR = "_anchor_name_reserved_in"
_MERGED_NAMESPACES_ATTR = "_merged_anchor_namespaces"


def _derived_names(holder: Any) -> set[str]:
    names = getattr(holder, _DERIVED_NAMES_ATTR, None)
    if names is None:
        names = set()
        object.__setattr__(holder, _DERIVED_NAMES_ATTR, names)
    return names


def _namespace_holder(anchor: Any) -> Any:
    """Owner if the anchor has one, else the unowned root of its derivation."""
    owner = getattr(anchor, _ANCHOR_OWNER_ATTR, None)
    if owner is not None:
        return owner
    return getattr(anchor, _NAMESPACE_ROOT_ATTR, None) or anchor


def _used_anchor_names(holder: Any) -> set[str]:
    used = set(_derived_names(holder))
    for existing in getattr(holder, "anchors", None) or []:
        used.add(existing.name.value)
    if not hasattr(holder, "anchors"):  # unowned root anchor
        used.add(holder.name.value)
    return used


def unique_derived_anchor_name(base: Any, candidate: str) -> str:
    """Reserve ``candidate`` (or ``candidate_2``, ``_3``...) in ``base``'s namespace."""
    holder = _namespace_holder(base)
    used = _used_anchor_names(holder)
    name, i = candidate, 2
    while name in used:
        name = f"{candidate}_{i}"
        i += 1
    _derived_names(holder).add(name)
    return name


def unique_derived_anchor_stem(base: Any, stem: str, count: int) -> str:
    """Reserve ``<stem>_0 .. <stem>_<count-1>`` as a block (patterns).

    The whole block moves to ``<stem>_2_<i>``, ``<stem>_3_<i>``... if any
    member is taken, so element names stay aligned with list indices.
    """
    holder = _namespace_holder(base)
    used = _used_anchor_names(holder)
    chosen, k = stem, 2
    while any(f"{chosen}_{i}" in used for i in range(count)):
        chosen = f"{stem}_{k}"
        k += 1
    _derived_names(holder).update(f"{chosen}_{i}" for i in range(count))
    return chosen


@register_method_fn("add_anchor_method")
def add_anchor_method(inst: Part | Assembly, anchor: Any) -> Any:
    """Attach an anchor to a part/assembly and take ownership of it.

    Raises ``ValueError`` if the name is already registered on ``inst`` or
    was generated for a different derived anchor of ``inst``.
    """
    name = anchor.name.value
    for existing in inst.anchors:
        if existing is anchor:
            return anchor
        if existing.name.value == name:
            raise ValueError(
                f"Anchor name '{name}' already exists on " f"'{inst.name.value}'."
            )
    derived = _derived_names(inst)
    merged = getattr(inst, _MERGED_NAMESPACES_ATTR, None) or []
    reserved_in = getattr(anchor, _RESERVED_IN_ATTR, None)
    own_reservation = reserved_in is derived or any(reserved_in is s for s in merged)
    if name in derived and not own_reservation:
        raise ValueError(
            f"Anchor name '{name}' is already used by a derived anchor on "
            f"'{inst.name.value}'; pick another name."
        )
    # An unowned anchor may carry names derived from it: merge them in.
    carried = getattr(anchor, _DERIVED_NAMES_ATTR, None)
    if carried:
        registered = {a.name.value for a in inst.anchors}
        for derived_name in carried:
            if derived_name in registered or derived_name in derived:
                raise ValueError(
                    f"Anchor '{name}' carries derived anchor '{derived_name}', "
                    f"which collides with an anchor on '{inst.name.value}'."
                )
        derived.update(carried)
        object.__setattr__(inst, _MERGED_NAMESPACES_ATTR, [*merged, carried])
    # Root the anchor frame under the owner frame unless the caller already
    # chained it (e.g. Anchor.from_plane roots under the plane frame, which
    # itself chains to the part frame).
    if anchor.frame.top_frame is None:
        anchor.frame.top_frame = inst.frame
    _set_anchor_owner(anchor, inst)
    inst.anchors.append(anchor)
    return anchor


@register_method_fn("get_anchor_method")
def get_anchor_method(inst: Part | Assembly, name: str) -> Any:
    """Look up an anchor by name."""
    for anchor in inst.anchors:
        if anchor.name.value == name:
            return anchor
    available = ", ".join(a.name.value for a in inst.anchors) or "<none>"
    raise ValueError(
        f"No anchor named '{name}' on '{inst.name.value}'. "
        f"Available anchors: {available}"
    )


@register_method_fn("anchor_from_plane")
def anchor_from_plane(inst: Any, plane: Any, name: str) -> Any:
    """Create an anchor on a plane (anchor Z = plane normal, X = plane X).

    Static method: ``inst`` is always None (run_method passes it for parity
    with instance methods).
    """
    from .gen.models import Anchor

    return Anchor(
        frame=Frame(
            top_frame=plane.frame,
            name=StringParameter(value=f"anchor_{name}_frame"),
            display=BoolParameter(value=False),
            position=[0.0, 0.0, 0.0],
            quaternion=[1.0, 0.0, 0.0, 0.0],
        ),
        name=StringParameter(value=name),
    )


def _derive_anchor(
    base: Any,
    name: str,
    position: Sequence[float],
    quaternion: Sequence[float],
) -> Any:
    """Create an anchor ``<base>_<name>`` whose frame is a child of ``base``'s.

    The name is made unique in the owner's anchor namespace (see the naming
    rule above ``add_anchor_method``).
    """
    derived_name = unique_derived_anchor_name(base, f"{base.name.value}_{name}")
    return make_child_anchor(base, derived_name, position, quaternion)


def make_child_anchor(
    base: Any,
    derived_name: str,
    position: Sequence[float],
    quaternion: Sequence[float],
) -> Any:
    """Anchor named exactly ``derived_name`` (already reserved) under ``base``."""
    from .gen.models import Anchor

    derived = Anchor(
        frame=Frame(
            top_frame=base.frame,
            name=StringParameter(value=f"anchor_{derived_name}_frame"),
            display=BoolParameter(value=False),
            position=[float(p) for p in position],
            quaternion=[float(q) for q in quaternion],
        ),
        name=StringParameter(value=derived_name),
    )
    holder = _namespace_holder(base)
    object.__setattr__(derived, _RESERVED_IN_ATTR, _derived_names(holder))
    owner = getattr(base, _ANCHOR_OWNER_ATTR, None)
    if owner is not None:
        _set_anchor_owner(derived, owner)
    else:
        object.__setattr__(derived, _NAMESPACE_ROOT_ATTR, holder)
    return derived


@register_method_fn("anchor_offset_method")
def anchor_offset_method(
    inst: Any, translation: Sequence[float], name: str = "offset"
) -> Any:
    """Derive an anchor translated in this anchor's local frame."""
    return _derive_anchor(inst, name, translation, [1.0, 0.0, 0.0, 0.0])


@register_method_fn("anchor_rotated_method")
def anchor_rotated_method(
    inst: Any,
    angle: float,
    axis: Sequence[float] = (0.0, 0.0, 1.0),
    name: str = "rotated",
) -> Any:
    """Derive an anchor rotated about an axis in this anchor's local frame."""
    return _derive_anchor(
        inst, name, [0.0, 0.0, 0.0], axis_angle_to_quaternion(list(axis), angle)
    )


@register_method_fn("anchor_flipped_method")
def anchor_flipped_method(inst: Any, name: str = "flipped") -> Any:
    """Derive an anchor with its Z axis reversed (180° about local X)."""
    return _derive_anchor(
        inst, name, [0.0, 0.0, 0.0], axis_angle_to_quaternion([1.0, 0.0, 0.0], math.pi)
    )


# --------------------------------------------------------------------------- #
# Joints: deterministic anchor-to-anchor placement (no constraint solver).
# A joint positions exactly one child component relative to an already-placed
# parent:  child_root = P ∘ J(dof) ∘ Flip? ∘ C⁻¹   with P the parent anchor in
# assembly space, J the DOF motion in the parent anchor frame, and C the child
# anchor in child-root space.
# --------------------------------------------------------------------------- #

_PLACED_IN_ATTR = "_placed_in"
_JOINT_ASSEMBLY_ATTR = "_joint_assembly"
_JOINT_CHILD_ROOT_ATTR = "_joint_child_root"
# Connections applied with add_connection (transient, never serialised): the
# interference check reads them to skip intended contacts, including
# loop-closing joints, which are not appended to ``joints``.
_APPLIED_CONNECTIONS_ATTR = "_applied_connections"

_IDENTITY_TF = ([0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0])


def _check_limits(value: float, limits: Any, label: str) -> None:
    if limits is None:
        return
    minimum = limits.min.value if limits.min is not None else None
    maximum = limits.max.value if limits.max is not None else None
    if minimum is not None and value < minimum:
        raise ValueError(f"Joint {label} {value} below limit {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"Joint {label} {value} above limit {maximum}")


def _validate_joint_limits(joint: Any) -> None:
    type_name = type(joint).__name__
    if type_name in ("RevoluteJoint", "ScrewJoint"):
        _check_limits(joint.angle.value, joint.limits, "angle")
    elif type_name == "SliderJoint":
        _check_limits(joint.offset.value, joint.limits, "offset")
    elif type_name in ("CylindricalJoint", "PinSlotJoint"):
        _check_limits(joint.angle.value, joint.angle_limits, "angle")
        _check_limits(joint.offset.value, joint.offset_limits, "offset")


def _joint_dof_tf(joint: Any) -> tuple[list[float], list[float]]:
    """DOF motion of a joint, expressed in the parent anchor frame."""
    type_name = type(joint).__name__
    if type_name == "RigidJoint":
        return _IDENTITY_TF
    if type_name == "RevoluteJoint":
        return [0.0, 0.0, 0.0], axis_angle_to_quaternion([0, 0, 1], joint.angle.value)
    if type_name == "SliderJoint":
        return [0.0, 0.0, joint.offset.value], [1.0, 0.0, 0.0, 0.0]
    if type_name == "CylindricalJoint":
        return (
            [0.0, 0.0, joint.offset.value],
            axis_angle_to_quaternion([0, 0, 1], joint.angle.value),
        )
    if type_name == "PlanarJoint":
        return (
            [joint.dx.value, joint.dy.value, 0.0],
            axis_angle_to_quaternion([0, 0, 1], joint.angle.value),
        )
    if type_name == "BallJoint":
        return [0.0, 0.0, 0.0], [float(v) for v in joint.orientation]
    if type_name == "PinSlotJoint":
        # Slide along the slot (parent +X), spin about the pin axis (+Z).
        return (
            [joint.offset.value, 0.0, 0.0],
            axis_angle_to_quaternion([0, 0, 1], joint.angle.value),
        )
    if type_name == "ScrewJoint":
        travel = joint.angle.value / (2.0 * math.pi) * joint.pitch.value
        return (
            [0.0, 0.0, travel],
            axis_angle_to_quaternion([0, 0, 1], joint.angle.value),
        )
    raise TypeError(f"Unsupported joint type '{type_name}'")


_ROOT_FRAMES_ATTR = "_root_frames"


def component_frames(component: Any) -> list[Any]:
    """Every frame standing for ``component``'s own coordinate system.

    A Part keeps its frame when placed. An Assembly gets a fresh root frame
    each time it is converted to an ``AssemblyRoot`` (placed in a parent, or
    serialised by ``to_dag``), and its children / anchors are re-rooted onto
    it. All of those frames are the same coordinate system, so anything that
    expresses a frame "in assembly space" must stop at whichever one the
    chain reaches.
    """
    source = getattr(component, _SOURCE_COMPONENT_ATTR, None) or component
    frames: list[Any] = []
    for frame in (
        component.frame,
        source.frame,
        *getattr(source, _ROOT_FRAMES_ATTR, ()),
    ):
        if not any(frame is f for f in frames):
            frames.append(frame)
    return frames


def tf_in_component(frame: Any, component: Any) -> tuple[list[float], list[float]]:
    """Transform of ``frame`` in ``component``'s own coordinates."""
    return tf_relative_to_frame(frame, component_frames(component))


_FOREIGN_JOINTS_ATTR = "_foreign_joints"


def _placed_chain(component: Any) -> list[Any]:
    """``component`` followed by every assembly it is (transitively) placed in."""
    chain = [component]
    while (parent := getattr(chain[-1], _PLACED_IN_ATTR, None)) is not None:
        if any(parent is c for c in chain):
            break
        chain.append(parent)
    return chain


def _placement_frame(component: Any, assembly: Any) -> Any:
    """The frame ``component`` was placed at inside ``assembly``."""
    for child in assembly.components:
        source = getattr(child, _SOURCE_COMPONENT_ATTR, None)
        if child is component or source is component:
            return child.frame
    raise ValueError(
        f"'{component.name.value}' is not a direct component of "
        f"'{assembly.name.value}'"
    )


def _tf_component_in_ancestor(
    component: Any, ancestor: Any
) -> tuple[list[float], list[float]]:
    """Transform of ``component``'s own coordinates in ``ancestor``'s, walking
    the placement chain (works across sub-assembly boundaries)."""
    t, q = _IDENTITY_TF
    cursor = component
    while cursor is not ancestor:
        parent = getattr(cursor, _PLACED_IN_ATTR)
        p_t, p_q = tf_in_component(_placement_frame(cursor, parent), parent)
        t, q = compose_tf(p_t, p_q, t, q)
        cursor = parent
    return t, q


def _common_ancestor(a: Any, b: Any) -> Optional[Any]:
    b_chain = _placed_chain(b)
    for candidate in _placed_chain(a):
        if any(candidate is c for c in b_chain):
            return candidate
    return None


def _parent_anchor_tf(joint: Any, assembly: Any) -> tuple[list[float], list[float]]:
    """Parent anchor of ``joint`` in ``assembly`` coordinates.

    Usually the anchor belongs to ``assembly`` or something placed under it.
    It may also belong to a *sibling* of ``assembly`` (e.g. a board Part next
    to a ``Components`` grouping sub-assembly): it is then resolved through
    the nearest assembly enclosing both, which must already hold both.
    """
    frame = joint.parent_anchor.frame
    try:
        return tf_in_component(frame, assembly)
    except ValueError:
        owner = _anchor_owner(joint.parent_anchor)
        ancestor = _common_ancestor(assembly, owner)
        if ancestor is None or ancestor is assembly:
            raise ValueError(
                f"Parent anchor '{joint.parent_anchor.name.value}' (on "
                f"'{owner.name.value}') does not chain up to "
                f"'{assembly.name.value}' and shares no common enclosing "
                "assembly with it. Place the parent component first (in this "
                "assembly, or next to it in an enclosing one)."
            ) from None
    a_t, a_q = compose_tf(
        *_tf_component_in_ancestor(owner, ancestor), *tf_in_component(frame, owner)
    )
    s_t, s_q = _tf_component_in_ancestor(assembly, ancestor)
    # Re-place this joint whenever something moves in the common ancestor.
    foreign = getattr(ancestor, _FOREIGN_JOINTS_ATTR, None)
    if foreign is None:
        foreign = []
        object.__setattr__(ancestor, _FOREIGN_JOINTS_ATTR, foreign)
    if not any(j is joint for j in foreign):
        foreign.append(joint)
    return compose_tf(*invert_tf(s_t, s_q), a_t, a_q)


def _resolve_joint_tf(joint: Any, assembly: Any) -> tuple[list[float], list[float]]:
    """Compute the child component's root transform in assembly space."""
    child_owner = _anchor_owner(joint.child_anchor)
    p_t, p_q = _parent_anchor_tf(joint, assembly)
    t, q = compose_tf(p_t, p_q, *_joint_dof_tf(joint))
    if joint.flip.value:
        t, q = compose_tf(
            t, q, [0.0, 0.0, 0.0], axis_angle_to_quaternion([1, 0, 0], math.pi)
        )
    c_t, c_q = tf_in_component(joint.child_anchor.frame, child_owner)
    return compose_tf(t, q, *invert_tf(c_t, c_q))


# --------------------------------------------------------------------------- #
# Re-resolution. A joint writes an ABSOLUTE placement for its child root (in
# assembly space), so moving a link does not by itself move what is jointed
# downstream of it. Whenever a joint's pose changes we therefore re-place
# every dependent joint:
#
# * inside the joint's assembly, ``assembly.joints`` is already in
#   topological order (a joint's parent must be placed before it is added),
#   so one forward pass over the joints after it suffices; a joint is
#   dependent when its parent or child anchor chains through a frame that
#   moved (a re-placed child root).
# * when that assembly is itself placed in a parent, the moved frames now sit
#   inside one of the parent's components: the same pass runs on the
#   parent's joints (re-placing e.g. the joint that mates the sub-assembly by
#   an anchor that moved), and so on up the tree.
#
# Re-resolution recomputes from scratch, so it is idempotent: resolving a
# joint whose inputs did not change is a no-op.
# --------------------------------------------------------------------------- #


def _chain_hits(frame: Any, moved: set[int]) -> bool:
    cursor = frame
    while cursor is not None:
        if id(cursor) in moved:
            return True
        cursor = cursor.top_frame
    return False


def _place_joint_child(joint: Any) -> Optional[Any]:
    """Recompute a placed joint's child root pose; return the moved frame."""
    assembly = getattr(joint, _JOINT_ASSEMBLY_ATTR, None)
    child_root = getattr(joint, _JOINT_CHILD_ROOT_ATTR, None)
    if assembly is None or child_root is None:
        return None
    t, q = _resolve_joint_tf(joint, assembly)
    child_root.frame.position = t
    child_root.frame.quaternion = q
    return child_root.frame


def _cascade(assembly: Any, moved: set[int], start: int = 0) -> None:
    """Re-place joints of ``assembly`` (from ``start``) that depend on a moved
    frame, then continue in the assembly's parent."""
    while assembly is not None:
        for joint in list(assembly.joints)[start:]:
            if _chain_hits(joint.parent_anchor.frame, moved) or _chain_hits(
                joint.child_anchor.frame, moved
            ):
                frame = _place_joint_child(joint)
                if frame is not None:
                    moved.add(id(frame))
        # Joints of sub-assemblies whose parent anchor sits on a sibling:
        # re-place unconditionally (idempotent) — either end may have moved.
        if moved:
            for joint in list(getattr(assembly, _FOREIGN_JOINTS_ATTR, ())):
                frame = _place_joint_child(joint)
                if frame is not None:
                    moved.add(id(frame))
        start = 0
        assembly = getattr(assembly, _PLACED_IN_ATTR, None)


def resolve_joint(joint: Any) -> bool:
    """Re-place ``joint``'s child, then everything jointed downstream of it.

    Returns False when the joint has not been added to an assembly yet.
    """
    frame = _place_joint_child(joint)
    if frame is None:
        return False
    assembly = getattr(joint, _JOINT_ASSEMBLY_ATTR)
    index = next(
        (i for i, j in enumerate(assembly.joints) if j is joint), len(assembly.joints)
    )
    _cascade(assembly, {id(frame)}, start=index + 1)
    return True


def _resolve_subtree(assembly: Any, moved: set[int]) -> None:
    """Re-place every joint of ``assembly`` and of its sub-assemblies."""
    for component in assembly.components:
        source = getattr(component, _SOURCE_COMPONENT_ATTR, None)
        if isinstance(source, Assembly) and source is not assembly:
            _resolve_subtree(source, moved)
    for joint in list(assembly.joints):
        frame = _place_joint_child(joint)
        if frame is not None:
            moved.add(id(frame))


@register_method_fn("joint_resolve_method")
def joint_resolve_method(inst: Any) -> bool:
    """Re-place this joint's child and cascade to dependent joints."""
    _validate_joint_limits(inst)
    return resolve_joint(inst)


@register_method_fn("assembly_resolve_method")
def assembly_resolve_method(inst: Any) -> bool:
    """Re-place every joint in this assembly (sub-assemblies first), then the
    joints of enclosing assemblies that depend on what moved. Relations of
    this assembly are re-enforced first (a DOF edited by hand follows its
    driver again)."""
    _enforce_relations(inst.relations)
    moved: set[int] = set()
    _resolve_subtree(inst, moved)
    _cascade(getattr(inst, _PLACED_IN_ATTR, None), moved)
    return True


@register_method_fn("add_joint_method")
def add_joint_method(inst: Assembly, joint: Any) -> bool:
    """Place a child component by connecting two anchors with a joint."""
    _validate_joint_limits(joint)
    parent_owner = _anchor_owner(joint.parent_anchor)
    child_owner = _anchor_owner(joint.child_anchor)
    if child_owner is inst:
        raise ValueError(
            "The child anchor of a joint cannot belong to the assembly itself; "
            "use assembly.ground(anchor) to fix a component to the assembly."
        )
    if parent_owner is child_owner:
        raise ValueError("A joint cannot connect a component to itself")
    placed_in = getattr(child_owner, _PLACED_IN_ATTR, None)
    if placed_in is not None:
        raise ValueError(
            f"Component '{child_owner.name.value}' is already placed "
            "(by add_component or another joint). A component can be "
            "positioned by at most one joint — connect further components "
            "to its anchors instead, or close the loop with "
            "assembly.add_connection(Connection(joint=...)), which checks that "
            "the two anchors already agree."
        )

    # The parent anchor must already chain to this assembly's frame (the
    # assembly itself, or a previously placed component), or belong to a
    # sibling placed in an enclosing assembly (resolved through the common
    # ancestor, see _parent_anchor_tf) — else this raises.
    t, q = _resolve_joint_tf(joint, inst)

    child_root = _convert_component_to_root(
        child_owner,
        parent_frame=inst.frame,
        component_path=(len(inst.components),),
    )
    # Joints are absolute placements: overwrite, don't compose (a translate()
    # done on the child before jointing is intentionally discarded).
    child_root.frame.position = t
    child_root.frame.quaternion = q
    inst.components.append(child_root)
    inst.joints.append(joint)

    object.__setattr__(child_owner, _PLACED_IN_ATTR, inst)
    object.__setattr__(joint, _JOINT_ASSEMBLY_ATTR, inst)
    object.__setattr__(joint, _JOINT_CHILD_ROOT_ATTR, child_root)
    return True


@register_method_fn("joint_set_value_method")
def joint_set_value_method(
    inst: Any, angle: float | None = None, offset: float | None = None
) -> bool:
    """Update a joint DOF value and re-resolve the child placement.

    When the joint is coupled by relations (see :func:`add_relation_method`),
    the related joints move with it: a driven DOF back-solves its driver, and
    every DOF downstream of that driver is recomputed.
    """
    updates: list[tuple[Any, str, float]] = []
    for dof, value in (("angle", angle), ("offset", offset)):
        if value is not None:
            root, root_dof, root_value = _back_solve(inst, dof, float(value))
            updates.extend(_relation_updates(root, root_dof, root_value))
    # Recompute from scratch (idempotent), then re-place everything jointed
    # downstream of each moved child, here and in enclosing assemblies.
    _apply_joint_values(updates, requested=inst)
    return True


# --------------------------------------------------------------------------- #
# Joint relations (Onshape "mate relations"). A relation couples one DOF of a
# driver joint to one DOF of a driven joint, linearly:
#     driven = k · driver + offset
# DOFs form a forest: each DOF is driven by at most one relation and the
# relations never loop, so setting any DOF has exactly one consistent answer
# — back-solve to the root driver, then recompute everything below it. Like
# joints, relations resolve at authoring time; the DAG carries the resulting
# frames plus the relation nodes for provenance.
# --------------------------------------------------------------------------- #

_ANGLE_JOINTS = ("RevoluteJoint", "CylindricalJoint", "ScrewJoint", "PinSlotJoint")
_OFFSET_JOINTS = ("SliderJoint", "CylindricalJoint", "PinSlotJoint")
# Transient (never serialised): relations a joint drives, and per DOF the
# relation driving it.
_DRIVES_ATTR = "_drives_relations"
_DRIVEN_BY_ATTR = "_driven_by_relation"

# relation type -> (driver field, driver DOF, driven field, driven DOF, gain field)
_RELATION_SPECS: dict[str, tuple[str, str, str, str, str]] = {
    "GearRelation": ("driver", "angle", "driven", "angle", "ratio"),
    "RackPinionRelation": ("pinion", "angle", "rack", "offset", "pitch_radius"),
    "ScrewRelation": ("screw", "angle", "nut", "offset", "pitch"),
    "LinearRelation": ("driver", "offset", "driven", "offset", "ratio"),
}

# Two requests for the same DOF agree when within this (rad or mm).
_RELATION_VALUE_TOL = 1e-9


def _relation_spec(relation: Any) -> tuple[str, str, str, str, str]:
    type_name = type(relation).__name__
    spec = _RELATION_SPECS.get(type_name)
    if spec is None:
        raise TypeError(f"Unsupported joint relation type '{type_name}'")
    return spec


def _relation_ends(relation: Any) -> tuple[tuple[Any, str], tuple[Any, str]]:
    """``((driver_joint, dof), (driven_joint, dof))`` of a relation."""
    driver_field, driver_dof, driven_field, driven_dof, _ = _relation_spec(relation)
    driver = getattr(relation, driver_field)
    driven = getattr(relation, driven_field)
    if driven is None:
        # ScrewRelation without a nut: a cylindrical joint's own offset.
        driven = driver
    return (driver, driver_dof), (driven, driven_dof)


def _relation_gain(relation: Any) -> float:
    """``k`` in ``driven = k · driver + offset``."""
    *_, gain_field = _relation_spec(relation)
    magnitude = float(getattr(relation, gain_field).value)
    if not magnitude > 0.0:
        raise ValueError(
            f"{type(relation).__name__}.{gain_field} must be > 0 (got "
            f"{magnitude}); use reverse=True to turn the driven joint the "
            "other way"
        )
    if type(relation).__name__ == "ScrewRelation":
        magnitude /= 2.0 * math.pi  # pitch is mm per turn
    return -magnitude if relation.reverse.value else magnitude


def _joint_label(joint: Any) -> str:
    """Human name of a joint: its type and the child anchor it places."""
    return f"{type(joint).__name__}('{joint.child_anchor.name.value}')"


def _check_relation_dof(relation: Any, joint: Any, dof: str, field: str) -> None:
    allowed = _ANGLE_JOINTS if dof == "angle" else _OFFSET_JOINTS
    type_name = type(joint).__name__
    if type_name not in allowed:
        raise ValueError(
            f"{type(relation).__name__}.{field} needs a joint with an {dof} "
            f"({', '.join(allowed)}), got {type_name}"
        )
    if getattr(joint, _JOINT_ASSEMBLY_ATTR, None) is None:
        raise ValueError(
            f"{type(relation).__name__}.{field}: {_joint_label(joint)} is not "
            "placed yet — add it with assembly.add_joint(...) before relating it"
        )


def _driven_relation(joint: Any, dof: str) -> Optional[Any]:
    return getattr(joint, _DRIVEN_BY_ATTR, {}).get(dof)


def _driven_dofs(joint: Any, dof: str) -> list[tuple[Any, Any, str]]:
    """``(relation, driven_joint, driven_dof)`` for every relation driven by
    ``joint``'s ``dof``."""
    out = []
    for relation in getattr(joint, _DRIVES_ATTR, ()):
        (_, driver_dof), (driven, driven_dof) = _relation_ends(relation)
        if driver_dof == dof:
            out.append((relation, driven, driven_dof))
    return out


def _back_solve(joint: Any, dof: str, value: float) -> tuple[Any, str, float]:
    """Walk up the relations driving ``joint.dof`` to the root driver and the
    value it needs for ``joint.dof`` to reach ``value``."""
    while (relation := _driven_relation(joint, dof)) is not None:
        (driver, driver_dof), _ = _relation_ends(relation)
        value = (value - float(relation.offset.value)) / _relation_gain(relation)
        joint, dof = driver, driver_dof
    return joint, dof, value


def _relation_updates(
    joint: Any, dof: str, value: float
) -> list[tuple[Any, str, float]]:
    """``(joint, dof, value)`` for ``joint.dof`` and every DOF it drives."""
    updates = [(joint, dof, value)]
    index = 0
    while index < len(updates):
        current, current_dof, current_value = updates[index]
        index += 1
        for relation, driven, driven_dof in _driven_dofs(current, current_dof):
            updates.append(
                (
                    driven,
                    driven_dof,
                    _relation_gain(relation) * current_value
                    + float(relation.offset.value),
                )
            )
    return updates


def _apply_joint_values(
    updates: list[tuple[Any, str, float]], requested: Optional[Any] = None
) -> None:
    """Write DOF values atomically (limits checked, all-or-nothing), then
    re-place each touched joint and what is jointed downstream of it."""
    from .gen.models import FloatParameter as FloatParam

    merged: dict[tuple[int, str], tuple[Any, str, float]] = {}
    for joint, dof, value in updates:
        key = (id(joint), dof)
        if key in merged and abs(merged[key][2] - value) > _RELATION_VALUE_TOL:
            raise ValueError(
                f"Conflicting values for the {dof} of {_joint_label(joint)} "
                f"({merged[key][2]:g} vs {value:g}): it is coupled by a "
                "relation to another value set in the same call — set only one"
            )
        merged[key] = (joint, dof, value)

    joints: list[Any] = []
    for joint, _, _ in merged.values():
        if not any(joint is j for j in joints):
            joints.append(joint)
    previous = [(joint, dof, getattr(joint, dof)) for joint, dof, _ in merged.values()]
    try:
        for joint, dof, value in merged.values():
            setattr(joint, dof, FloatParam(value=float(value)))
        for joint in joints:
            try:
                _validate_joint_limits(joint)
            except ValueError as exc:
                if joint is requested or len(joints) == 1:
                    raise
                raise ValueError(
                    f"{exc} on {_joint_label(joint)}, which a joint relation "
                    "moves with this change; nothing was changed"
                ) from None
    except ValueError:
        for joint, dof, old in previous:
            setattr(joint, dof, old)
        raise
    for joint in joints:
        resolve_joint(joint)


def _enforce_relations(relations: Sequence[Any]) -> None:
    """Recompute every DOF driven by ``relations`` from its root driver."""
    updates: list[tuple[Any, str, float]] = []
    for relation in relations:
        (driver, driver_dof), _ = _relation_ends(relation)
        root, root_dof, root_value = _back_solve(
            driver, driver_dof, float(getattr(driver, driver_dof).value)
        )
        updates.extend(_relation_updates(root, root_dof, root_value))
    if updates:
        _apply_joint_values(updates)


@register_method_fn("add_relation_method")
def add_relation_method(inst: Assembly, relation: Any) -> bool:
    """Couple two placed joints with a relation and enforce it right away.

    The driven DOF is recomputed from the driver (``driven = k · driver +
    offset``); afterwards ``set_angle`` / ``set_offset`` on either joint moves
    both. Raises when a joint lacks the DOF, is not placed yet, the driven DOF
    is already driven by another relation, or the relation would close a
    cycle.
    """
    type_name = type(relation).__name__
    driver_field, _, driven_field, _, _ = _relation_spec(relation)
    (driver, driver_dof), (driven, driven_dof) = _relation_ends(relation)
    _check_relation_dof(relation, driver, driver_dof, driver_field)
    _check_relation_dof(relation, driven, driven_dof, driven_field)
    if driven is driver and driven_dof == driver_dof:
        raise ValueError(f"{type_name}: a joint cannot drive its own {driven_dof}")
    _relation_gain(relation)  # validates the ratio / pitch up front

    existing = _driven_relation(driven, driven_dof)
    if existing is not None:
        raise ValueError(
            f"{type_name}: the {driven_dof} of {_joint_label(driven)} is already "
            f"driven by a {type(existing).__name__}; a joint value can follow "
            "only one relation (chain them instead: A drives B, B drives C)"
        )
    # Adding driver -> driven closes a cycle iff driver is downstream of driven.
    stack = [(driven, driven_dof)]
    while stack:
        joint, dof = stack.pop()
        if joint is driver and dof == driver_dof:
            raise ValueError(
                f"{type_name}: relating {_joint_label(driver)} to "
                f"{_joint_label(driven)} closes a cycle of relations — "
                f"{_joint_label(driven)} already drives it"
            )
        stack.extend((j, d) for _, j, d in _driven_dofs(joint, dof))

    drives = getattr(driver, _DRIVES_ATTR, None)
    if drives is None:
        drives = []
        object.__setattr__(driver, _DRIVES_ATTR, drives)
    drives.append(relation)
    driven_by = getattr(driven, _DRIVEN_BY_ATTR, None)
    if driven_by is None:
        driven_by = {}
        object.__setattr__(driven, _DRIVEN_BY_ATTR, driven_by)
    driven_by[driven_dof] = relation
    inst.relations.append(relation)
    try:
        _enforce_relations([relation])
    except ValueError:
        # The driven joint cannot reach the value (limits): undo the coupling.
        for holder in (drives, inst.relations):
            holder[:] = [r for r in holder if r is not relation]
        del driven_by[driven_dof]
        raise
    return True


def _is_placed_in(owner: Any, assembly: Any) -> bool:
    """True when ``owner`` is ``assembly`` itself or already has a placement."""
    return owner is assembly or getattr(owner, _PLACED_IN_ATTR, None) is not None


@register_method_fn("add_connection_method")
def add_connection_method(
    inst: Assembly,
    connection: Any,
    pos_tol: float = DEFAULT_POS_TOL,
    angle_tol_deg: float = DEFAULT_ANGLE_TOL_DEG,
) -> bool:
    """Apply a library-defined connection: geometry modifiers, then the joint.

    Three shapes of connection:

    * **placing** -- the joint's child component is not placed yet: the joint
      places it (exactly like :func:`add_joint_method`).
    * **loop-closing** -- both components are already placed (the far end of a
      rail between two legs, a slat screwed to its second rail): the joint
      places nothing. Its anchors must already agree up to the joint's free
      DOFs, within ``pos_tol`` mm / ``angle_tol_deg`` degrees, else
      :class:`LoopClosureError`. The joint is not added to ``inst.joints``.
    * **joint-less** -- ``joint`` is None: only the modifiers apply
      (fastening- or cut-only).

    Modifiers run first so contributed operations land on the parts before the
    joint placement. Parts that were already placed need no special handling:
    their converted root shares the live ``operations`` list (see
    :func:`_bind_live_fields`). A loop closure is checked before any modifier
    runs, so a failing connection leaves the parts untouched.
    """
    joint = connection.joint
    closes_loop = False
    if joint is not None:
        child_owner = _anchor_owner(joint.child_anchor)
        parent_owner = _anchor_owner(joint.parent_anchor)
        closes_loop = _is_placed_in(child_owner, inst)
        if closes_loop:
            if not _is_placed_in(parent_owner, inst):
                raise ValueError(
                    f"Connection '{connection.name.value}': child component "
                    f"'{child_owner.name.value}' is already placed but parent "
                    f"'{parent_owner.name.value}' is not. Swap parent_anchor and "
                    "child_anchor so the joint places the unplaced component."
                )
            _validate_joint_limits(joint)
            check_loop_closure(
                joint,
                inst,
                pos_tol=pos_tol,
                angle_tol_deg=angle_tol_deg,
                label=connection.name.value,
            )

    for modifier in connection.modifiers:
        owner = _anchor_owner(modifier.anchor)
        if not isinstance(owner, Part):
            raise ValueError(
                f"PartModifier anchor '{modifier.anchor.name.value}' must belong "
                f"to a Part, not {type(owner).__name__}: connections can only "
                "modify part geometry."
            )
        owner.add_operations(modifier.operations)
    applied = getattr(inst, _APPLIED_CONNECTIONS_ATTR, None)
    if applied is None:
        applied = []
        object.__setattr__(inst, _APPLIED_CONNECTIONS_ATTR, applied)
    applied.append(connection)
    if joint is None or closes_loop:
        return True
    return add_joint_method(inst, joint)


@register_method_fn("ground_method")
def ground_method(
    inst: Assembly,
    anchor: Any,
    at: Optional[Sequence[float]] = None,
    rot_deg: Any = None,
    quaternion: Optional[Sequence[float]] = None,
) -> bool:
    """Fix a component to the assembly via a rigid joint.

    The component moves so that ``anchor`` coincides with the assembly frame
    translated by ``at`` (mm) and rotated by ``rot_deg`` (degrees, see
    :func:`cadbuildr.foundation.placement.rotation_from_deg`) or by
    ``quaternion`` (``[w, x, y, z]``). Axes are aligned, not mated
    face-to-face. Defaults: the assembly origin.
    """
    from .gen.models import Anchor, RigidJoint

    if rot_deg is not None and quaternion is not None:
        raise TypeError("ground: pass either rot_deg= or quaternion=, not both")
    position = _normalize_vector(at, 3) if at is not None else [0.0, 0.0, 0.0]
    if quaternion is not None:
        quaternion = _normalize_vector(quaternion, 4)
    else:
        quaternion = (
            rotation_from_deg(rot_deg) if rot_deg is not None else [1.0, 0.0, 0.0, 0.0]
        )
    origin_anchor = Anchor(
        frame=Frame(
            top_frame=inst.frame,
            name=StringParameter(value=f"anchor_ground_{len(inst.joints)}_frame"),
            display=BoolParameter(value=False),
            position=position,
            quaternion=quaternion,
        ),
        name=StringParameter(value=f"ground_{len(inst.joints)}"),
    )
    _set_anchor_owner(origin_anchor, inst)
    joint = RigidJoint(
        parent_anchor=origin_anchor,
        child_anchor=anchor,
        flip=BoolParameter(value=False),
    )
    return add_joint_method(inst, joint)


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
    from .gen.models import FixedTranslationConstraint

    vector = _normalize_vector(translation, 3)
    quat = _normalize_vector(quaternion, 4)
    inst.constraints.append(
        FixedTranslationConstraint(
            component=component, translation=vector, quaternion=quat
        )
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
def paint_method(
    inst: Part | Assembly, color: ColorSpec, transparency: float = 0.5
) -> bool:
    """Paint a part (creates Material instance).

    ``color`` may be a named color, a hex string (e.g. ``"#212121"``), or an
    ``[r, g, b]`` sequence; see :func:`cadbuildr.foundation.constants.resolve_color`.
    """
    global _material_counter
    from .gen.models import Material, MaterialOptions

    # Resolve named color / hex string / [r, g, b] to an RGB triple.
    diffuse_color = resolve_color(color)

    # Create Material instance
    _material_counter += 1
    material = Material(
        name=f"Material_{_material_counter}",
        painted_node_ids=[],
        options=MaterialOptions(
            diffuse_color=diffuse_color, transparency=float(transparency)
        ),
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
def rotate_method(
    inst: Part | Assembly, angle: float, axis: Sequence[float] = (0.0, 0.0, 1.0)
) -> bool:
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
    inst: Part | Assembly,
    memo: dict[str, Any] | None = None,
    with_source: bool = False,
) -> dict[str, Any]:
    """Convert Part or Assembly to raw DAG dictionary (not formatted with version/rootNodeId).

    ``with_source`` attaches recorded source locations (``src`` / ``fieldSrc``,
    see ``cadbuildr.foundation.source_capture``) to the nodes; ids are unchanged.
    """
    from .source_capture import suspended

    # Objects built while serializing are not user code: record no source.
    with suspended():
        return _to_dag(inst, memo, with_source)


def _to_dag(
    inst: Part | Assembly, memo: dict[str, Any] | None, with_source: bool
) -> dict[str, Any]:
    from .foundation_hooks import setup_foundation_hooks
    from .gen.dag import pydantic_to_dag
    from .constants import DEFAULT_TYPE_REGISTRY

    if memo is None:
        memo = {}

    hooks = setup_foundation_hooks()
    type_registry = DEFAULT_TYPE_REGISTRY.copy()

    # Convert to root if needed
    from .compute_functions import _convert_component_to_root

    if isinstance(inst, (Part, Assembly)):
        inst = _convert_component_to_root(inst)

    # Resolve slug-name collisions across the full tree before serializing.
    _finalize_root_names(inst)

    pydantic_to_dag(inst, memo, type_registry, hooks, with_source=with_source)

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
    from .gen.models import StringParameter

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


def _user_class_slug(
    component: Any, base_class_names: tuple[str, ...]
) -> Optional[str]:
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


# --------------------------------------------------------------------------- #
# Live components. ``add_component`` / ``add_joint`` convert a Part/Assembly to
# a PartRoot/AssemblyRoot when it is placed (placement math needs the root's
# frame), but the user keeps editing the *Part*: ``part.add_operation(...)``
# after placement must still reach the DAG. Two mechanisms keep the root live:
#
# 1. The root shares the source's list objects (operations, planes, anchors,
#    joints) instead of pydantic's validation-time copies, so appends through
#    either object are visible to both — even to a bare ``pydantic_to_dag``.
# 2. Every root remembers its source; re-converting a root (which ``to_dag``,
#    ``show_dag``, ``show`` and the BOM do on the whole tree before
#    serialising) re-syncs what sharing cannot cover: lists the user rebound,
#    a ``paint()`` done after placement, and components added to a
#    sub-assembly after the sub-assembly itself was placed.
# --------------------------------------------------------------------------- #

_SOURCE_COMPONENT_ATTR = "_source_component"
_LIVE_PART_FIELDS = ("operations", "planes", "anchors", "interfaces")
_LIVE_ASSEMBLY_FIELDS = ("anchors", "interfaces", "joints", "relations")


def _bind_live_fields(root: Any, source: Any, fields: tuple[str, ...]) -> None:
    """Make ``root.<field>`` the very list object held by ``source.<field>``."""
    for field in fields:
        value = getattr(source, field)
        if getattr(root, field) is not value:
            # Bypass pydantic: assignment would not copy today, but the
            # identity of the list is the whole point here.
            object.__setattr__(root, field, value)


def _sync_material(root: Any, source: Any) -> None:
    material = getattr(source, "_material", None)
    if material is not None:
        root.material = material
    _sync_library(root, source)


# Instance attribute holding the ``LibraryRef`` a library configurable
# (``cadbuildr.foundation.library``) stamps on the Part/Assembly it built.
_LIBRARY_REF_ATTR = "_library_ref"


def _library_ref_of(component: Any) -> Any:
    return (
        component.__dict__.get(_LIBRARY_REF_ATTR)
        if hasattr(component, "__dict__")
        else None
    )


def _sync_library(root: Any, source: Any) -> None:
    ref = _library_ref_of(source)
    if ref is not None:
        root.library = ref


def _inherit_component_source(root: Any, component: Any) -> None:
    """A root stands for the user's Part/Assembly: point it at that object's
    construction site (``source_capture``), not at the conversion call."""
    from .gen.dag.conversion import SOURCE_ATTR

    meta = component.__dict__.get(SOURCE_ATTR)
    if meta and meta.get("src"):
        root.__dict__[SOURCE_ATTR] = {"src": meta["src"]}


def _sync_name(root: Any, source: Any, default: str) -> None:
    """A name the user set on the Part / Assembly after placing it (``leg.name
    = ...`` in the assembly's ``__init__``) wins over the root's copy, which
    was taken at placement. Default names keep the root's generated name."""
    name = getattr(source, "name", None)
    value = getattr(name, "value", None)
    if value is None or value == default or value == root.name.value:
        return
    root.name = name
    if hasattr(root, _AUTO_SLUG_ATTR):
        object.__delattr__(root, _AUTO_SLUG_ATTR)


def _sync_part_root(root: PartRoot) -> None:
    source = getattr(root, _SOURCE_COMPONENT_ATTR, None)
    if source is None:
        return
    _bind_live_fields(root, source, _LIVE_PART_FIELDS)
    _sync_material(root, source)
    _sync_name(root, source, "part0")


def _convert_component_to_root(
    component: Any,
    parent_frame: Optional[Frame] = None,
    component_path: tuple[int, ...] = (),
) -> Optional[PartRoot | AssemblyRoot]:
    """Convert Part/Assembly instances to their root representations.

    Converting an existing root re-syncs it (and, for an assembly, its whole
    subtree) with the live Part/Assembly it was created from, so edits made
    after placement are reflected.

    Args:
        component: Part or Assembly to convert
        parent_frame: Optional parent frame (assembly frame) that component frame should point to
    """
    from .gen.models import Frame, StringParameter, BoolParameter

    if isinstance(component, PartRoot):
        # Component is already a PartRoot, but we may need to update its frame's top_frame
        if parent_frame is not None and component.frame.top_frame != parent_frame:
            # Update the frame's top_frame to point to parent
            component.frame.top_frame = parent_frame
        _sync_part_root(component)
        return component
    if isinstance(component, AssemblyRoot):
        if parent_frame is not None:
            # Update this assembly's frame's top_frame
            component.frame.top_frame = parent_frame
        source = getattr(component, _SOURCE_COMPONENT_ATTR, None)
        if source is not None:
            # Components added to the source after it was placed (their frames
            # point at the source's own frame) join the root here.
            children = list(source.components)
            _bind_live_fields(component, source, _LIVE_ASSEMBLY_FIELDS)
            _sync_material(component, source)
            _sync_name(component, source, "assembly0")
            for anchor in source.anchors:
                if anchor.frame.top_frame is source.frame:
                    anchor.frame.top_frame = component.frame
        elif parent_frame is not None:
            children = list(component.components)
        else:
            return component
        # Recursively convert/update nested components
        component.components = [
            _convert_component_to_root(
                child,
                parent_frame=component.frame,
                component_path=component_path + (idx,),
            )
            for idx, child in enumerate(children)
        ]
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
            anchors=component.anchors,  # Anchor frames also chain through component.frame
            interfaces=component.interfaces,
            material=getattr(component, "_material", None),
            library=_library_ref_of(component),
        )
        if auto_slug is not None:
            object.__setattr__(part_root, _AUTO_SLUG_ATTR, auto_slug)
        object.__setattr__(part_root, _SOURCE_COMPONENT_ATTR, component)
        _inherit_component_source(part_root, component)
        _bind_live_fields(part_root, component, _LIVE_PART_FIELDS)
        return part_root
    if isinstance(component, Assembly):
        # Create assembly frame first
        original_frame = component.frame
        unique_frame_name = f"assembly_{_format_component_path(component_path)}_frame"

        # KEEP the assembly's position - it represents the transform applied to this assembly
        assembly_frame = Frame(
            top_frame=(
                original_frame.top_frame if parent_frame is None else parent_frame
            ),
            name=StringParameter(value=unique_frame_name),
            display=BoolParameter(value=original_frame.display.value),
            position=(
                original_frame.position.copy()
                if isinstance(original_frame.position, list)
                else original_frame.position
            ),
            quaternion=(
                original_frame.quaternion.copy()
                if isinstance(original_frame.quaternion, list)
                else original_frame.quaternion
            ),
        )

        # Unlike Part conversion (frame updated in place), the assembly gets a
        # fresh frame — re-root direct anchors onto it so they keep following
        # the assembly. Derived anchors chain through their base anchor.
        previous_frames = component_frames(component)
        for anchor in component.anchors:
            if any(anchor.frame.top_frame is f for f in previous_frames):
                anchor.frame.top_frame = assembly_frame
        object.__setattr__(
            component,
            _ROOT_FRAMES_ATTR,
            [*getattr(component, _ROOT_FRAMES_ATTR, ()), assembly_frame],
        )
        # The children are re-rooted onto ``assembly_frame`` below, so
        # ``original_frame`` no longer sits on their chain. Record that both
        # frames are one coordinate system: ``tf_relative_to_frame(x,
        # assembly.frame)`` (and so ``assembly.check()`` /
        # ``check_interference(assembly)``) keeps working once the assembly
        # is nested or serialised.
        link_frame_aliases(original_frame, assembly_frame)

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
            anchors=component.anchors,
            interfaces=component.interfaces,
            joints=component.joints,
            relations=component.relations,
            material=getattr(component, "_material", None),
            library=_library_ref_of(component),
        )
        if auto_assembly_slug is not None:
            object.__setattr__(assembly_root, _AUTO_SLUG_ATTR, auto_assembly_slug)
        object.__setattr__(assembly_root, _SOURCE_COMPONENT_ATTR, component)
        _inherit_component_source(assembly_root, component)
        _bind_live_fields(assembly_root, component, _LIVE_ASSEMBLY_FIELDS)
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
def add_component_method(
    inst: Assembly,
    component: Any,
    tf: Any = None,
    at: Optional[Sequence[float]] = None,
    rot_deg: Any = None,
) -> bool:
    """Add a component (part or assembly) to an assembly.

    Place it either with ``tf`` (a transform dict / 4x4 matrix / ``TFHelper``)
    or with the explicit pose keywords -- not both:

    * ``rot_deg`` -- rotation in **degrees** about the component's own origin:
      a number (about +Z) or ``(rx, ry, rz)`` about the fixed X, Y, Z axes,
      applied in that order;
    * ``at`` -- then a translation ``(x, y, z)`` in mm, in assembly space.
    """
    if tf is not None and (at is not None or rot_deg is not None):
        raise TypeError("add_component: pass either tf= or at=/rot_deg=, not both")
    component_root = _convert_component_to_root(
        component,
        parent_frame=inst.frame,
        component_path=(len(inst.components),),
    )
    if tf is not None:
        translation, quaternion = _parse_component_tf(tf)
    else:
        translation = _normalize_vector(at, 3) if at is not None else None
        quaternion = rotation_from_deg(rot_deg) if rot_deg is not None else None
    if translation is not None:
        _apply_translation_to_root(component_root, translation)
    if quaternion is not None:
        _apply_rotation_to_root(component_root, quaternion)
    inst.components.append(component_root)
    if isinstance(component, (Part, Assembly)):
        # Mark placement so a later add_joint on the same component errors
        # instead of silently double-placing it.
        object.__setattr__(component, _PLACED_IN_ATTR, inst)
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
            from .math_utils import rotation_matrix_to_quaternion

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
def get_parallel_plane_method(
    inst: Plane, distance: float, name: str = "parallel"
) -> Plane:
    """Create a plane parallel to this plane, offset by ``distance`` along its normal.

    The new frame is a CHILD of this plane's frame, so its transform is purely
    local: ``[0, 0, distance]`` along the parent's Z (normal), identity rotation.
    The kernel composes ``world = parent_world · local``; baking the parent's
    position/quaternion in here as well applied the parent transform twice
    (only harmless for an identity parent such as a bare ``part.xy()``).
    """
    return Plane(
        frame=Frame(
            top_frame=inst.frame,
            name=StringParameter(value=f"frame_{name}"),
            display=BoolParameter(value=False),
            position=[0.0, 0.0, float(distance)],
            quaternion=[1.0, 0.0, 0.0, 0.0],  # Same orientation as the parent
        ),
        name=StringParameter(value=name),
        display=BoolParameter(value=False),
    )


def _plane_world_quaternion(inst: Plane) -> list[float]:
    """Orientation of the plane's frame composed up its ``top_frame`` chain.

    Derived planes (``get_parallel_plane`` / ``get_angle_plane_from_axis``)
    store a LOCAL transform relative to their parent plane, so the frame's own
    quaternion is not the plane's orientation — compose the chain.
    """
    _, quaternion = tf_relative_to_frame(inst.frame)
    return quaternion


@register_method_fn("get_plane_x_axis")
def get_plane_x_axis(inst: Plane) -> list[float]:
    """Get the X-axis of the plane's frame."""
    x_axis, _, _ = quaternion_to_axes(_plane_world_quaternion(inst))
    return x_axis


@register_method_fn("get_plane_y_axis")
def get_plane_y_axis(inst: Plane) -> list[float]:
    """Get the Y-axis of the plane's frame."""
    _, y_axis, _ = quaternion_to_axes(_plane_world_quaternion(inst))
    return y_axis


@register_method_fn("get_plane_z_axis")
def get_plane_z_axis(inst: Plane) -> list[float]:
    """Get the Z-axis (normal) of the plane's frame."""
    _, _, z_axis = quaternion_to_axes(_plane_world_quaternion(inst))
    return z_axis


@register_method_fn("get_angle_plane_from_axis_method")
def get_angle_plane_from_axis_method(
    inst: Plane, axis: Sequence[float], angle: float, name: str = "rotated"
) -> Plane:
    """Create a plane rotated by ``angle`` (radians) around ``axis``.

    ``axis`` is expressed in THIS plane's local coordinates (``[0, 0, 1]`` is
    the plane normal, ``[1, 0, 0]`` its X axis) and passes through the plane
    origin. The new frame is a child of this plane's frame, so the rotation is
    stored as a purely local quaternion; pre-multiplying the parent quaternion
    here as well applied the parent rotation twice.
    """
    return Plane(
        frame=Frame(
            top_frame=inst.frame,
            name=StringParameter(value=f"frame_{name}"),
            display=BoolParameter(value=False),
            position=[0.0, 0.0, 0.0],  # Rotation only, about the parent origin
            quaternion=axis_angle_to_quaternion(axis, angle),
        ),
        name=StringParameter(value=name),
        display=BoolParameter(value=False),  # Don't display construction planes
    )


# --------------------------------------------------------------------------- #
# Hole wizard (TappedHole / ClearanceHole) — ISO metric tables in holes.py.
# --------------------------------------------------------------------------- #


@register_compute_fn("compute_tap_drill_radius")
def compute_tap_drill_radius(inst: Any, field_name: str, meta: dict[str, Any]) -> Any:
    from .holes import tap_drill_diameter

    return FloatParameter(value=tap_drill_diameter(inst.thread_size.value) / 2.0)


@register_compute_fn("compute_clearance_radius")
def compute_clearance_radius(inst: Any, field_name: str, meta: dict[str, Any]) -> Any:
    from .holes import clearance_diameter

    return FloatParameter(value=clearance_diameter(inst.size.value, inst.fit) / 2.0)


# --------------------------------------------------------------------------- #
# Extrusion cap-face planes (FC-5): sketch on top of a pad without computing
# offsets by hand.
# --------------------------------------------------------------------------- #


def _extrusion_span(inst: Any) -> tuple[float, float]:
    start, end = inst.start.value, inst.end.value
    cond = str(getattr(inst.end_condition, "value", inst.end_condition)).upper()
    if cond == "SYMMETRIC":
        return -end / 2.0, end / 2.0
    if cond.startswith("THROUGH_ALL"):
        raise ValueError(
            "Cap-face planes of a THROUGH_ALL extrusion depend on the rest of the part; "
            "use a BLIND or SYMMETRIC extrusion"
        )
    return start, end


@register_method_fn("extrusion_end_face_plane")
def extrusion_end_face_plane(inst: Any) -> Any:
    _, end = _extrusion_span(inst)
    return inst.sketch.plane.get_parallel_plane(end, name="end_face")


@register_method_fn("extrusion_start_face_plane")
def extrusion_start_face_plane(inst: Any) -> Any:
    start, _ = _extrusion_span(inst)
    return inst.sketch.plane.get_parallel_plane(start, name="start_face")


# --------------------------------------------------------------------------- #
# Part shortcuts (FC-12): build an operation, add it, return it.
# --------------------------------------------------------------------------- #


def _p3(v: Any) -> Any:
    from .gen.models import Point3D

    return v if isinstance(v, Point3D) else Point3D(x=v[0], y=v[1], z=v[2])


@register_method_fn("part_extrude_method")
def part_extrude_method(
    inst: Any, shape: Any, depth: float, cut: bool = False, end_condition: Any = None
) -> Any:
    from .gen.models import Extrusion

    kwargs = {"cut": cut}
    if end_condition is not None:
        kwargs["end_condition"] = end_condition
    op = Extrusion(shape, depth, **kwargs)
    inst.add_operation(op)
    return op


@register_method_fn("part_cut_extrude_method")
def part_cut_extrude_method(
    inst: Any, shape: Any, depth: float, end_condition: Any = None
) -> Any:
    return part_extrude_method(
        inst, shape, depth, cut=True, end_condition=end_condition
    )


@register_method_fn("part_revolve_method")
def part_revolve_method(
    inst: Any, shape: Any, axis: Any, angle: float = 360.0, cut: bool = False
) -> Any:
    from .gen.models import Axis, Lathe, Line

    if isinstance(axis, Line):
        axis = Axis(axis)
    kwargs = {"cut": cut}
    if abs(angle - 360.0) > 1e-9:
        kwargs["angle"] = angle
    op = Lathe(shape, axis, **kwargs)
    inst.add_operation(op)
    return op


def _fillet_radius_points(points: Any) -> Any:
    """``radius_points`` as FilletRadiusPoint nodes: accepts ``(position, radius)`` pairs."""
    from .gen.models import FilletRadiusPoint

    if points is None:
        return None
    out = []
    for pt in points:
        if isinstance(pt, FilletRadiusPoint):
            out.append(pt)
            continue
        position, radius = pt
        if not 0.0 < float(position) < 1.0:
            raise ValueError(
                f"radius_points: position {position} must be strictly between 0 (the edge's start, "
                "set by `radius`) and 1 (its end, set by `radius_end`)"
            )
        if float(radius) <= 0.0:
            raise ValueError(f"radius_points: radius {radius} must be positive")
        out.append(FilletRadiusPoint(position=float(position), radius=float(radius)))
    return out


def _make_fillet(
    solid: Any, radius: float, edges: Any, radius_end: Any, radius_points: Any
) -> Any:
    from .gen.models import Fillet

    kwargs: dict = {"solid": solid, "radius": radius, "edge_finder": edges}
    if radius_end is not None:
        kwargs["radius_end"] = radius_end
    if radius_points is not None:
        kwargs["radius_points"] = _fillet_radius_points(radius_points)
    return Fillet(**kwargs)


@register_method_fn("part_fillet_method")
def part_fillet_method(
    inst: Any,
    solid: Any,
    radius: float,
    edges: Any = None,
    radius_end: Any = None,
    radius_points: Any = None,
) -> Any:
    op = _make_fillet(solid, radius, edges, radius_end, radius_points)
    inst.add_operation(op)
    return op


@register_method_fn("part_chamfer_method")
def part_chamfer_method(
    inst: Any, solid: Any, distance: float, edges: Any = None
) -> Any:
    from .gen.models import Chamfer

    op = Chamfer(solid=solid, radius=distance, edge_finder=edges)
    inst.add_operation(op)
    return op


@register_method_fn("part_fillet_edges_method")
def part_fillet_edges_method(
    inst: Any,
    radius: float,
    edges: Any = None,
    radius_end: Any = None,
    radius_points: Any = None,
) -> Any:
    """Round edges of the part's body built so far (all edges, or those ``edges`` selects).

    ``radius_end`` / ``radius_points`` make it a variable fillet: ``radius`` at
    each edge's start, ``radius_end`` at its end, ``(position, radius)`` pairs in
    between (position 0..1 along the edge)."""
    if not inst.operations:
        raise ValueError("fillet_edges: add the features to round before the fillet")
    op = _make_fillet(None, radius, edges, radius_end, radius_points)
    inst.add_operation(op)
    return op


@register_method_fn("part_chamfer_edges_method")
def part_chamfer_edges_method(inst: Any, distance: float, edges: Any = None) -> Any:
    """Bevel edges of the part's body built so far (all edges, or those ``edges`` selects)."""
    from .gen.models import Chamfer

    if not inst.operations:
        raise ValueError("chamfer_edges: add the features to bevel before the chamfer")
    op = Chamfer(radius=distance, edge_finder=edges)
    inst.add_operation(op)
    return op


@register_method_fn("part_chamfer_vertices_method")
def part_chamfer_vertices_method(inst: Any, distance: float, at: Any = None) -> Any:
    """Bevel corners of the part's body built so far (vertex chamfer / corner setback).

    ``at`` lists the corners as ``(x, y, z)`` points (or Point3D); ``None`` bevels
    every convex corner where three straight edges meet."""
    from .gen.models import Point3D, VertexChamfer

    if not inst.operations:
        raise ValueError(
            "chamfer_vertices: add the features to bevel before the chamfer"
        )
    if float(distance) <= 0.0:
        raise ValueError(f"chamfer_vertices: distance {distance} must be positive")
    vertices = None
    if at is not None:
        vertices = [
            p if isinstance(p, Point3D) else Point3D(*(float(c) for c in p)) for p in at
        ]
        if not vertices:
            raise ValueError(
                "chamfer_vertices: `at` is empty — pass None to bevel every corner"
            )
    op = VertexChamfer(distance=distance, vertices=vertices)
    inst.add_operation(op)
    return op


@register_method_fn("part_shell_method")
def part_shell_method(
    inst: Any, solid: Any, thickness: float, faces: Any = None
) -> Any:
    from .gen.models import Shell

    op = Shell(solid=solid, thickness=thickness, face_finder=faces)
    inst.add_operation(op)
    return op


def _check_body_pattern(inst: Any, shape: Any, method: str) -> None:
    """shape=None patterns the part's body so far: it needs features before it."""
    if shape is None and not inst.operations:
        raise ValueError(
            f"{method}: shape=None repeats the part's body; add features before the pattern"
        )


@register_method_fn("part_linear_pattern_method")
def part_linear_pattern_method(
    inst: Any,
    shape: Any,
    direction: Any,
    count: int,
    spacing: float,
    direction2: Any = None,
    count2: int = 1,
    spacing2: float = 0.0,
) -> Any:
    from .gen.models import LinearPattern

    _check_body_pattern(inst, shape, "linear_pattern")
    if direction2 is None and count2 > 1:
        raise ValueError("linear_pattern: count2 > 1 needs a direction2")
    kwargs = {}
    if direction2 is not None:
        kwargs = {"direction2": _p3(direction2), "count2": count2, "spacing2": spacing2}
    op = LinearPattern(shape, _p3(direction), count, spacing, **kwargs)
    inst.add_operation(op)
    return op


@register_method_fn("part_polar_pattern_method")
def part_polar_pattern_method(
    inst: Any, shape: Any, count: int, angle: float = 360.0, axis: Any = (0.0, 0.0, 1.0)
) -> Any:
    from .gen.models import PolarPattern

    _check_body_pattern(inst, shape, "polar_pattern")
    op = PolarPattern(shape, count, angle=angle, axis_direction=_p3(axis))
    inst.add_operation(op)
    return op


def _body_list(method: str, bodies: Any) -> list:
    """One operation or a list of them (the bodies to select)."""
    out = list(bodies) if isinstance(bodies, (list, tuple)) else [bodies]
    if not out:
        raise ValueError(f"{method}: pass at least one body (an operation of the part)")
    return out


@register_method_fn("part_delete_bodies_method")
def part_delete_bodies_method(inst: Any, bodies: Any) -> Any:
    """Delete the part's bodies that share volume with ``bodies`` (one op or a list)."""
    from .gen.models import DeleteBodies

    if not inst.operations:
        raise ValueError("delete_bodies: add the bodies to delete before deleting them")
    op = DeleteBodies(_body_list("delete_bodies", bodies))
    inst.add_operation(op)
    return op


@register_method_fn("part_keep_bodies_method")
def part_keep_bodies_method(inst: Any, bodies: Any) -> Any:
    """Keep only the part's bodies that share volume with ``bodies`` (one op or a list)."""
    from .gen.models import KeepBodies

    if not inst.operations:
        raise ValueError("keep_bodies: add the bodies to keep before selecting them")
    op = KeepBodies(_body_list("keep_bodies", bodies))
    inst.add_operation(op)
    return op


@register_method_fn("part_curve_pattern_method")
def part_curve_pattern_method(
    inst: Any, shape: Any, path: Any, count: int, align_to_path: bool = False
) -> Any:
    from .gen.models import CurvePattern

    _check_body_pattern(inst, shape, "curve_pattern")
    op = CurvePattern(shape, path, count, align_to_path=align_to_path)
    inst.add_operation(op)
    return op


@register_compute_fn("compute_rib_lines")
def compute_rib_lines(inst: Any, field_name: str, meta: dict[str, Any]) -> list:
    """Closed outline of a Rib: the polyline plus the chord back to its start."""
    from .gen.models import Line

    pts = list(inst.points)
    if len(pts) < 3:
        raise ValueError(
            "Rib needs at least 3 points (two segments and the closing chord)"
        )
    return [Line(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
