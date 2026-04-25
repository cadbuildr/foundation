"""Draw class (pencil API) for easier sketch drawing - copied from old foundation."""

import math
from typing import TYPE_CHECKING, List
import numpy as np

if TYPE_CHECKING:
    from .gen.models import (
        Sketch,
        Point,
        Line,
        Arc,
        Spline,
        Polygon,
        CustomClosedShape,
    )

from .gen.models import Point, Line, Arc, Spline, Polygon, CustomClosedShape


class Draw:
    """Small utils to make it easier to draw points and lines in a sketch."""

    def __init__(self, sketch: "Sketch"):
        self.sketch = sketch
        self.x = 0.0
        self.y = 0.0
        self.point_added = False
        self.point_idx = 0
        self.points: List[Point] = []
        self.primitives: List[Line | Arc | Spline] = []

    def reset(self) -> None:
        self.x = 0.0
        self.y = 0.0
        self.point_added = False
        self.point_idx = 0
        self.points = []
        self.primitives = []

    def move_to(self, x: float, y: float) -> None:
        """Move to absolute position"""
        self.x = x
        self.y = y
        self.point_added = False

    def move(self, dx: float, dy: float) -> None:
        """Relative move"""
        self.x += dx
        self.y += dy
        self.point_added = False

    def add_point(self) -> None:
        if self.x == 0.0 and self.y == 0.0:
            point = self.sketch.origin
        else:
            point = Point(self.sketch, self.x, self.y)
        self.points.append(point)
        self.point_idx = len(self.points) - 1

    @staticmethod
    def _points_are_close(p1: Point, p2: Point, tol: float = 1e-6) -> bool:
        """Return True if two points are effectively the same."""
        dx = p1.x.value - p2.x.value
        dy = p1.y.value - p2.y.value
        return abs(dx) <= tol and abs(dy) <= tol

    def line_to(self, x: float, y: float) -> None:
        """Draw a line to absolute position (x, y)."""
        if not self.point_added:
            self.add_point()
        self.x = x
        self.y = y
        self.add_point()
        self.point_added = True
        self.primitives.append(Line(self.points[-2], self.points[-1]))
        return

    def line(self, dx: float, dy: float) -> None:
        """Draw a line with relative move (dx, dy)."""
        if not self.point_added:
            self.add_point()
        self.x += dx
        self.y += dy
        self.add_point()
        self.point_added = True
        self.primitives.append(Line(self.points[-2], self.points[-1]))
        return

    def arc_to(self, x: float, y: float, radius: float) -> None:
        """Draw arc to absolute position (x, y) with given radius"""
        if not self.point_added:
            self.add_point()
        self.x = x
        self.y = y
        self.add_point()
        self.point_added = True
        # Use Arc.from_two_points_and_radius static method
        from .gen.models import Arc, FloatParameter

        arc = Arc.from_two_points_and_radius(
            self.points[-2], self.points[-1], FloatParameter(value=radius)
        )
        if arc is None:
            raise ValueError("Failed to create arc from radius")
        self.primitives.append(arc)
        return

    def arc(self, dx: float, dy: float, radius: float) -> None:
        """Draw arc with relative movement (dx, dy) and given radius"""
        if not self.point_added:
            self.add_point()
        self.x += dx
        self.y += dy
        self.add_point()
        self.point_added = True
        # Use Arc.from_two_points_and_radius static method
        from .gen.models import Arc, FloatParameter

        arc = Arc.from_two_points_and_radius(
            self.points[-2], self.points[-1], FloatParameter(value=radius)
        )
        if arc is None:
            raise ValueError("Failed to create arc from radius")
        self.primitives.append(arc)
        return

    def back_one_point(self) -> None:
        self.point_idx -= 1
        if self.point_idx < 0:
            self.point_idx = 0

    def get_closed_polygon(self) -> Polygon:
        """Get a closed polygon from the drawn lines."""
        lines: List[Line] = []

        # Check that all the primitives are lines and filter them into a new list
        for primitive in self.primitives:
            if not isinstance(primitive, Line):
                raise ValueError("All primitives must be lines for get_closed_polygon")
            lines.append(primitive)

        if len(self.points) > 0 and not self._points_are_close(
            self.points[0], self.points[-1]
        ):
            lines.append(Line(self.points[-1], self.points[0]))
        return Polygon(lines)

    def get_closed_shape(self) -> CustomClosedShape:
        """Return a closed shape using the primitives and closes it with a line if needed."""
        primitives = list(self.primitives)
        if len(self.points) > 0 and not self._points_are_close(
            self.points[0], self.points[-1]
        ):
            primitives.append(Line(self.points[-1], self.points[0]))
        return CustomClosedShape(primitives)

    def close(self) -> CustomClosedShape:
        """Close the current drawing and return a CustomClosedShape."""
        return self.get_closed_shape()

    def close_with_mirror(self) -> CustomClosedShape:
        """Mirror the primitives to close the shape symmetrically based on axis from first to last point."""
        if len(self.points) < 2:
            raise ValueError("At least two points are required to perform mirroring.")

        # Determine the axis of symmetry
        start_point = self.points[0]
        end_point = self.points[-1]

        mirrored_primitives: List[Line | Arc | Spline] = []

        for primitive in self.primitives:
            if hasattr(primitive, "mirror"):
                mirrored_primitives.append(primitive.mirror(start_point, end_point))
            else:
                # Fallback for primitives without mirror method
                mirrored_primitives.append(primitive)

        all_primitives = self.primitives + mirrored_primitives[::-1]

        return CustomClosedShape(all_primitives)

    def tangent_arc(self, dx: float, dy: float) -> None:
        """Draw an arc tangentially to the last primitive, relative move."""
        self.tangent_arc_to(self.x + dx, self.y + dy)

    def tangent_arc_to(self, x: float, y: float) -> None:
        """Draw an arc tangentially to the last primitive, ending at (x, y)."""
        if not self.point_added:
            self.add_point()

        if len(self.primitives) == 0:
            raise ValueError("No previous primitive to draw tangent arc from")

        p1 = self.points[-1]
        p2 = Point(self.sketch, x, y)

        if p1.x.value == p2.x.value and p1.y.value == p2.y.value:
            raise ValueError("Destination point is the same as previous one")

        # Get tangent from last primitive
        last_prim = self.primitives[-1]
        if not hasattr(last_prim, "tangent"):
            raise ValueError("Last primitive does not have a tangent method")

        tangent_vector = last_prim.tangent()
        if tangent_vector is None:
            raise ValueError("Failed to compute tangent for last primitive")
        tangent_unit_vector = np.asarray(tangent_vector, dtype=float)
        bisector_line = self._calculate_perpendicular_bisector(p1, p2)
        perpendicular_line_through_p1 = self._calculate_perpendicular_line(
            p1, tangent_unit_vector
        )

        # Calculate intersection
        center = self._line_intersection(bisector_line, perpendicular_line_through_p1)

        if center is None:
            raise ValueError("Cannot determine the center of the arc")

        # Calculate angles from the center to p1 and p2
        angle1 = math.atan2(p1.y.value - center.y.value, p1.x.value - center.x.value)
        angle2 = math.atan2(p2.y.value - center.y.value, p2.x.value - center.x.value)

        # Normalize the angular difference to be between -π and π
        delta_angle = (angle2 - angle1 + math.pi) % (2 * math.pi) - math.pi

        mid_angle = angle1 + delta_angle / 2

        mid_radius = math.sqrt(
            (p1.x.value - center.x.value) ** 2 + (p1.y.value - center.y.value) ** 2
        )
        mid_x = center.x.value + mid_radius * math.cos(mid_angle)
        mid_y = center.y.value + mid_radius * math.sin(mid_angle)
        intermediate_point = Point(self.sketch, mid_x, mid_y)

        arc = Arc(p1, intermediate_point, p2)

        self._update_state_after_arc(p2, arc)

    def _calculate_perpendicular_bisector(self, p1: Point, p2: Point) -> Line:
        """Calculate the perpendicular bisector of the line segment connecting p1 and p2."""
        midpoint_x = (p1.x.value + p2.x.value) / 2
        midpoint_y = (p1.y.value + p2.y.value) / 2
        midpoint = Point(self.sketch, midpoint_x, midpoint_y)

        # Calculate the direction vector of the line p1 -> p2
        dx = p2.x.value - p1.x.value
        dy = p2.y.value - p1.y.value

        # Calculate the length of the direction vector
        length = math.sqrt(dx**2 + dy**2)
        if length == 0:
            raise ValueError("The length of the direction vector is zero")

        # Calculate the unit vector perpendicular to the direction vector
        unit_perpendicular = np.array([-dy / length, dx / length])

        # Create the perpendicular bisector line
        bisector_line = Line(
            midpoint,
            Point(
                self.sketch,
                midpoint_x + unit_perpendicular[0],
                midpoint_y + unit_perpendicular[1],
            ),
        )

        return bisector_line

    def _calculate_perpendicular_line(
        self, point: Point, tangent_unit_vector: np.ndarray
    ) -> Line:
        """Calculate the line perpendicular to the tangent vector passing through the given point."""
        return Line(
            point,
            Point(
                self.sketch,
                point.x.value - tangent_unit_vector[1],
                point.y.value + tangent_unit_vector[0],
            ),
        )

    def _line_intersection(self, line1: Line, line2: Line) -> "Point | None":
        """Calculate the intersection point of two lines."""
        p1, p2 = line1.p1, line1.p2
        p3, p4 = line2.p1, line2.p2

        x1, y1 = p1.x.value, p1.y.value
        x2, y2 = p2.x.value, p2.y.value
        x3, y3 = p3.x.value, p3.y.value
        x4, y4 = p4.x.value, p4.y.value

        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-10:
            return None  # Lines are parallel

        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom

        ix = x1 + t * (x2 - x1)
        iy = y1 + t * (y2 - y1)

        return Point(self.sketch, ix, iy)

    def _update_state_after_arc(self, end_point: Point, arc: Arc):
        """Update the state after creating an arc."""
        self.x = end_point.x.value
        self.y = end_point.y.value
        self.points.append(end_point)
        self.primitives.append(arc)
        self.point_added = True

    def rounded_corner_then_line(self, dx: float, dy: float, radius: float) -> None:
        """Draw a rounded corner followed by a line, relative move."""
        self.rounded_corner_then_line_to(self.x + dx, self.y + dy, radius)

    def rounded_corner_then_line_to(self, x: float, y: float, radius: float) -> None:
        """Draw a rounded corner followed by a line, ending at (x, y)."""
        if not self.point_added:
            self.add_point()
        if len(self.primitives) == 0:
            raise ValueError("No previous line to round the corner of")

        last_primitive = self.primitives[-1]
        if not isinstance(last_primitive, Line):
            raise NotImplementedError("Rounded corners are only implemented for lines")

        # Shorten the last line by radius
        new_p2 = self._shorten_last_line(radius)
        self.primitives[-1] = Line(last_primitive.p1, new_p2)
        self.points[-1] = new_p2

        # Calculate where the arc should end
        arc_end_point = self._calculate_arc_end_point(x, y, radius)

        # Draw tangent arc from shortened line to arc_end_point
        self.x = new_p2.x.value
        self.y = new_p2.y.value
        self.tangent_arc_to(arc_end_point.x.value, arc_end_point.y.value)

        # If arc doesn't reach final point, draw line to it
        if abs(self.x - x) > 1e-6 or abs(self.y - y) > 1e-6:
            self.line_to(x, y)

    def _shorten_last_line(self, radius: float) -> Point:
        """Shorten the last line primitive by the given radius."""
        last_primitive = self.primitives[-1]
        p1 = last_primitive.p1
        p2 = last_primitive.p2

        line_dx = p2.x.value - p1.x.value
        line_dy = p2.y.value - p1.y.value
        line_length = math.sqrt(line_dx**2 + line_dy**2)

        if line_length < radius:
            raise ValueError(
                "The radius is too large compared to the length of the previous line segment"
            )

        shorten_factor = (line_length - radius) / line_length
        new_x = p1.x.value + line_dx * shorten_factor
        new_y = p1.y.value + line_dy * shorten_factor
        new_p2 = Point(self.sketch, new_x, new_y)

        return new_p2

    def _calculate_arc_end_point(self, x: float, y: float, radius: float) -> Point:
        """Calculate the endpoint for the tangent arc."""
        dx = x - self.x
        dy = y - self.y
        new_line_length = math.sqrt(dx**2 + dy**2)

        if new_line_length < radius:
            raise ValueError(
                f"The radius ({radius}) is too large compared to the length of the new line segment ({new_line_length})"
            )

        unit_dx = dx / new_line_length
        unit_dy = dy / new_line_length

        arc_end_x = self.x + radius * unit_dx
        arc_end_y = self.y + radius * unit_dy

        return Point(self.sketch, arc_end_x, arc_end_y)
