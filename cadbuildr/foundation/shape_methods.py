"""2D Shape transformation methods (rotate, translate) for foundation schema."""

import math
from typing import Optional
from .gen.runtime import register_method_fn
from .gen.models import (
    Point,
    Line,
    Arc,
    Spline,
    Circle,
    Ellipse,
    EllipseArc,
    Polygon,
    CustomClosedShape,
    FloatParameter,
    Frame,
    Plane,
    StringParameter,
    BoolParameter,
)
from .math_utils import rotation_matrix_to_quaternion


# =================================================
# POINT METHODS
# =================================================


@register_method_fn("point_translate")
def point_translate(inst: Point, dx: float, dy: float) -> Point:
    """Translate a point by (dx, dy)."""
    return Point(
        sketch=inst.sketch,
        x=FloatParameter(value=inst.x.value + dx),
        y=FloatParameter(value=inst.y.value + dy),
    )


@register_method_fn("point_rotate")
def point_rotate(inst: Point, angle: float, center: Optional[Point] = None) -> Point:
    """Rotate a point around a center point (angle in radians)."""
    if center is None:
        center = inst.sketch.origin

    dx = inst.x.value - center.x.value
    dy = inst.y.value - center.y.value

    return Point(
        sketch=inst.sketch,
        x=FloatParameter(
            value=center.x.value + dx * math.cos(angle) - dy * math.sin(angle)
        ),
        y=FloatParameter(
            value=center.y.value + dx * math.sin(angle) + dy * math.cos(angle)
        ),
    )


# =================================================
# LINE METHODS
# =================================================


@register_method_fn("line_translate")
def line_translate(inst: Line, dx: float, dy: float) -> Line:
    """Translate a line by (dx, dy)."""
    return Line(p1=inst.p1.translate(dx, dy), p2=inst.p2.translate(dx, dy))


@register_method_fn("line_rotate")
def line_rotate(inst: Line, angle: float, center: Optional[Point] = None) -> Line:
    """Rotate a line around a center point."""
    if center is None:
        center = inst.sketch.origin
    return Line(p1=inst.p1.rotate(angle, center), p2=inst.p2.rotate(angle, center))


@register_method_fn("line_tangent")
def line_tangent(inst: Line) -> list[float]:
    """Calculate the tangent unit vector of the line."""
    import numpy as np

    dx = inst.p2.x.value - inst.p1.x.value
    dy = inst.p2.y.value - inst.p1.y.value
    u = np.array([dx, dy])
    norm = np.linalg.norm(u)
    if norm == 0:
        return [0.0, 0.0]
    # Return as list, not numpy array (for JSON serialization)
    result = u / norm
    return result.tolist()


@register_method_fn("line_get_extrusion_plane_method")
def line_get_extrusion_plane_method(
    inst: Line,
    extrusion_direction: Optional[list[float]] = None,
    name: str = "line_extrusion_plane",
) -> Plane:
    """Build a 3D plane from a 2D sketch line and extrusion direction.

    The resulting plane:
    - origin is at the line start point (p1) in sketch coordinates
    - x-axis follows the line direction (p1 -> p2)
    - y-axis follows the extrusion direction projected orthogonal to x
    """
    import numpy as np

    if extrusion_direction is None:
        extrusion_direction = [0.0, 0.0, 1.0]
    elif hasattr(extrusion_direction, "tolist"):
        extrusion_direction = extrusion_direction.tolist()

    if not isinstance(extrusion_direction, (list, tuple)) or len(extrusion_direction) != 3:
        raise ValueError("extrusion_direction must be a 3D vector")

    # Line direction in sketch-local coordinates.
    line_vec = np.array(
        [
            inst.p2.x.value - inst.p1.x.value,
            inst.p2.y.value - inst.p1.y.value,
            0.0,
        ],
        dtype=float,
    )
    line_norm = np.linalg.norm(line_vec)
    if line_norm == 0:
        raise ValueError("Cannot build an extrusion plane from a zero-length line")
    x_axis = line_vec / line_norm

    y_hint = np.array(extrusion_direction, dtype=float)
    y_hint_norm = np.linalg.norm(y_hint)
    if y_hint_norm == 0:
        raise ValueError("extrusion_direction cannot be the zero vector")
    y_hint = y_hint / y_hint_norm

    # Remove x component so y is orthogonal to the line direction.
    y_axis = y_hint - np.dot(y_hint, x_axis) * x_axis
    y_norm = np.linalg.norm(y_axis)
    if y_norm < 1e-9:
        raise ValueError(
            "extrusion_direction cannot be parallel to the line direction"
        )
    y_axis = y_axis / y_norm

    z_axis = np.cross(x_axis, y_axis)
    z_norm = np.linalg.norm(z_axis)
    if z_norm < 1e-9:
        raise ValueError(
            "Failed to construct a valid plane basis from line and extrusion direction"
        )
    z_axis = z_axis / z_norm

    rot_matrix = np.array([x_axis, y_axis, z_axis]).T
    quaternion = rotation_matrix_to_quaternion(rot_matrix)

    # Line points are sketch-local; this frame is relative to the sketch plane frame.
    frame = Frame(
        top_frame=inst.sketch.plane.frame,
        name=StringParameter(value=f"{name}_frame"),
        display=BoolParameter(value=False),
        position=[inst.p1.x.value, inst.p1.y.value, 0.0],
        quaternion=quaternion,
    )
    return Plane(
        frame=frame,
        name=StringParameter(value=name),
        display=BoolParameter(value=False),
    )


# =================================================
# ARC METHODS
# =================================================


@register_method_fn("arc_translate")
def arc_translate(inst: Arc, dx: float, dy: float) -> Arc:
    """Translate an arc by (dx, dy)."""
    return Arc(
        p1=inst.p1.translate(dx, dy),
        p2=inst.p2.translate(dx, dy),
        p3=inst.p3.translate(dx, dy),
    )


@register_method_fn("arc_rotate")
def arc_rotate(inst: Arc, angle: float, center: Optional[Point] = None) -> Arc:
    """Rotate an arc around a center point."""
    if center is None:
        center = inst.sketch.origin
    return Arc(
        p1=inst.p1.rotate(angle, center),
        p2=inst.p2.rotate(angle, center),
        p3=inst.p3.rotate(angle, center),
    )


@register_method_fn("arc_tangent")
def arc_tangent(inst: Arc) -> list[float]:
    """Calculate the tangent unit vector at p3 (end point) of the arc."""
    import numpy as np

    # Get center of arc from 3 points
    def get_arc_center(p1, p2, p3):
        """Get the center of an arc from 3 points."""
        A = np.array(
            [
                [p1.x.value**2 + p1.y.value**2, p1.x.value, p1.y.value, 1],
                [p2.x.value**2 + p2.y.value**2, p2.x.value, p2.y.value, 1],
                [p3.x.value**2 + p3.y.value**2, p3.x.value, p3.y.value, 1],
            ]
        )

        M11 = np.linalg.det(A[:, 1:4])
        if abs(M11) < 1e-10:
            # Points are aligned, treat as line
            dx = p3.x.value - p1.x.value
            dy = p3.y.value - p1.y.value
            norm = np.sqrt(dx**2 + dy**2)
            if norm == 0:
                return None, np.array([0.0, 0.0])
            return None, np.array([dx / norm, dy / norm])

        M12 = np.linalg.det(A[np.ix_(range(3), [0, 2, 3])])
        M13 = np.linalg.det(A[np.ix_(range(3), [0, 1, 3])])

        x0 = 0.5 * M12 / M11
        y0 = -0.5 * M13 / M11

        return (x0, y0), None

    center, tangent_line = get_arc_center(inst.p1, inst.p2, inst.p3)

    if center is None:
        # Degenerate case: points are aligned
        return tangent_line.tolist()

    # Calculate tangent at p3
    dx = inst.p3.x.value - center[0]
    dy = inst.p3.y.value - center[1]

    # Determine if arc is counterclockwise
    # Cross product of (p1-center) and (p2-center)
    v1 = np.array([inst.p1.x.value - center[0], inst.p1.y.value - center[1]])
    v2 = np.array([inst.p2.x.value - center[0], inst.p2.y.value - center[1]])
    cross = v1[0] * v2[1] - v1[1] * v2[0]

    if cross > 0:
        # Counterclockwise: rotate radius vector 90 degrees CCW
        tangent_x = -dy
        tangent_y = dx
    else:
        # Clockwise: rotate radius vector 90 degrees CW
        tangent_x = dy
        tangent_y = -dx

    # Normalize
    norm = np.sqrt(tangent_x**2 + tangent_y**2)
    if norm == 0:
        return [0.0, 0.0]

    # Return as list, not numpy array (for JSON serialization)
    return [tangent_x / norm, tangent_y / norm]


# =================================================
# SPLINE METHODS
# =================================================


@register_method_fn("spline_translate")
def spline_translate(inst: Spline, dx: float, dy: float) -> Spline:
    """Translate a spline by (dx, dy)."""
    return Spline(points=[point.translate(dx, dy) for point in inst.points])


@register_method_fn("spline_rotate")
def spline_rotate(inst: Spline, angle: float, center: Optional[Point] = None) -> Spline:
    """Rotate a spline around a center point."""
    if center is None:
        center = inst.sketch.origin
    return Spline(points=[point.rotate(angle, center) for point in inst.points])


# =================================================
# CIRCLE METHODS
# =================================================


@register_method_fn("circle_translate")
def circle_translate(inst: Circle, dx: float, dy: float) -> Circle:
    """Translate a circle by (dx, dy)."""
    return Circle(center=inst.center.translate(dx, dy), radius=inst.radius)


@register_method_fn("circle_rotate")
def circle_rotate(inst: Circle, angle: float, center: Optional[Point] = None) -> Circle:
    """Rotate a circle around a center point."""
    if center is None:
        center = inst.sketch.origin
    return Circle(center=inst.center.rotate(angle, center), radius=inst.radius)


# =================================================
# ELLIPSE METHODS
# =================================================


@register_method_fn("ellipse_translate")
def ellipse_translate(inst: Ellipse, dx: float, dy: float) -> Ellipse:
    """Translate an ellipse by (dx, dy)."""
    return Ellipse(center=inst.center.translate(dx, dy), a=inst.a, b=inst.b)


@register_method_fn("ellipse_rotate")
def ellipse_rotate(inst: Ellipse, angle: float, center: Optional[Point] = None) -> Ellipse:
    """Rotate an ellipse around a center point."""
    if center is None:
        center = inst.sketch.origin
    return Ellipse(center=inst.center.rotate(angle, center), a=inst.a, b=inst.b)


# =================================================
# ELLIPSE ARC METHODS
# =================================================


@register_method_fn("ellipse_arc_translate")
def ellipse_arc_translate(inst, dx: float, dy: float):
    """Translate an ellipse arc by (dx, dy)."""
    return EllipseArc(
        center=inst.center.translate(dx, dy),
        a=inst.a,
        b=inst.b,
        start_angle=inst.start_angle,
        end_angle=inst.end_angle,
    )


@register_method_fn("ellipse_arc_rotate")
def ellipse_arc_rotate(inst, angle: float, center=None):
    """Rotate an ellipse arc around a center point."""
    if center is None:
        center = inst.sketch.origin
    return EllipseArc(
        center=inst.center.rotate(angle, center),
        a=inst.a,
        b=inst.b,
        start_angle=inst.start_angle,
        end_angle=inst.end_angle,
    )


# =================================================
# POLYGON METHODS
# =================================================


@register_method_fn("polygon_translate")
def polygon_translate(inst: Polygon, dx: float, dy: float) -> Polygon:
    """Translate a polygon by (dx, dy)."""
    return Polygon(lines=[line.translate(dx, dy) for line in inst.lines])


@register_method_fn("polygon_rotate")
def polygon_rotate(inst: Polygon, angle: float, center: Optional[Point] = None) -> Polygon:
    """Rotate a polygon around a center point."""
    if center is None:
        center = inst.sketch.origin
    return Polygon(lines=[line.rotate(angle, center) for line in inst.lines])


# =================================================
# CUSTOM CLOSED SHAPE METHODS
# =================================================


@register_method_fn("custom_closed_shape_translate")
def custom_closed_shape_translate(inst: CustomClosedShape, dx: float, dy: float) -> CustomClosedShape:
    """Translate a custom closed shape by (dx, dy)."""
    return CustomClosedShape(
        primitives=[prim.translate(dx, dy) for prim in inst.primitives]
    )


@register_method_fn("custom_closed_shape_rotate")
def custom_closed_shape_rotate(
    inst: CustomClosedShape, angle: float, center: Optional[Point] = None
) -> CustomClosedShape:
    """Rotate a custom closed shape around a center point."""
    if center is None:
        center = inst.sketch.origin
    return CustomClosedShape(
        primitives=[prim.rotate(angle, center) for prim in inst.primitives]
    )
