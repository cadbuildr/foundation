"""2D Shape transformation methods (rotate, translate) for foundation schema."""

import math
from .gen.runtime import register_method_fn, register_compute_fn
from .gen.models import (
    Point,
    Line,
    Arc,
    Circle,
    Ellipse,
    Polygon,
    CustomClosedShape,
    FloatParameter,
)


# =================================================
# POINT METHODS
# =================================================


@register_method_fn("point_translate")
def point_translate(inst, dx: float, dy: float):
    """Translate a point by (dx, dy)."""
    return Point(
        sketch=inst.sketch,
        x=FloatParameter(value=inst.x.value + dx),
        y=FloatParameter(value=inst.y.value + dy),
    )


@register_method_fn("point_rotate")
def point_rotate(inst, angle: float, center=None):
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
def line_translate(inst, dx: float, dy: float):
    """Translate a line by (dx, dy)."""
    return Line(p1=inst.p1.translate(dx, dy), p2=inst.p2.translate(dx, dy))


@register_method_fn("line_rotate")
def line_rotate(inst, angle: float, center=None):
    """Rotate a line around a center point."""
    if center is None:
        center = inst.sketch.origin
    return Line(p1=inst.p1.rotate(angle, center), p2=inst.p2.rotate(angle, center))


@register_method_fn("line_tangent")
def line_tangent(inst):
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


# =================================================
# ARC METHODS
# =================================================


@register_method_fn("arc_translate")
def arc_translate(inst, dx: float, dy: float):
    """Translate an arc by (dx, dy)."""
    return Arc(
        p1=inst.p1.translate(dx, dy),
        p2=inst.p2.translate(dx, dy),
        p3=inst.p3.translate(dx, dy),
    )


@register_method_fn("arc_rotate")
def arc_rotate(inst, angle: float, center=None):
    """Rotate an arc around a center point."""
    if center is None:
        center = inst.sketch.origin
    return Arc(
        p1=inst.p1.rotate(angle, center),
        p2=inst.p2.rotate(angle, center),
        p3=inst.p3.rotate(angle, center),
    )


@register_method_fn("arc_tangent")
def arc_tangent(inst):
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
        return tangent_line

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
# CIRCLE METHODS
# =================================================


@register_method_fn("circle_translate")
def circle_translate(inst, dx: float, dy: float):
    """Translate a circle by (dx, dy)."""
    return Circle(center=inst.center.translate(dx, dy), radius=inst.radius)


@register_method_fn("circle_rotate")
def circle_rotate(inst, angle: float, center=None):
    """Rotate a circle around a center point."""
    if center is None:
        center = inst.sketch.origin
    return Circle(center=inst.center.rotate(angle, center), radius=inst.radius)


# =================================================
# ELLIPSE METHODS
# =================================================


@register_method_fn("ellipse_translate")
def ellipse_translate(inst, dx: float, dy: float):
    """Translate an ellipse by (dx, dy)."""
    return Ellipse(center=inst.center.translate(dx, dy), a=inst.a, b=inst.b)


@register_method_fn("ellipse_rotate")
def ellipse_rotate(inst, angle: float, center=None):
    """Rotate an ellipse around a center point."""
    if center is None:
        center = inst.sketch.origin
    return Ellipse(center=inst.center.rotate(angle, center), a=inst.a, b=inst.b)


# =================================================
# POLYGON METHODS
# =================================================


@register_method_fn("polygon_translate")
def polygon_translate(inst, dx: float, dy: float):
    """Translate a polygon by (dx, dy)."""
    return Polygon(lines=[line.translate(dx, dy) for line in inst.lines])


@register_method_fn("polygon_rotate")
def polygon_rotate(inst, angle: float, center=None):
    """Rotate a polygon around a center point."""
    if center is None:
        center = inst.sketch.origin
    return Polygon(lines=[line.rotate(angle, center) for line in inst.lines])


# =================================================
# CUSTOM CLOSED SHAPE METHODS
# =================================================


@register_method_fn("custom_closed_shape_translate")
def custom_closed_shape_translate(inst, dx: float, dy: float):
    """Translate a custom closed shape by (dx, dy)."""
    return CustomClosedShape(
        primitives=[prim.translate(dx, dy) for prim in inst.primitives]
    )


@register_method_fn("custom_closed_shape_rotate")
def custom_closed_shape_rotate(inst, angle: float, center=None):
    """Rotate a custom closed shape around a center point."""
    if center is None:
        center = inst.sketch.origin
    return CustomClosedShape(
        primitives=[prim.rotate(angle, center) for prim in inst.primitives]
    )
