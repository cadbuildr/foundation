from cadbuildr.foundation.sketch.point import Point
from cadbuildr.foundation.sketch.primitives.line import Line
from cadbuildr.foundation.sketch.primitives.arc import Arc
from cadbuildr.foundation.sketch.closed_sketch_shape import (
    Polygon,
    CustomClosedShape,
    SketchPrimitiveTypes,
)
from cadbuildr.foundation.exceptions import (
    InternalStateException,
    GeometryException,
    InvalidParameterValueException,
)
import numpy as np
import math

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from cadbuildr.foundation.sketch.sketch import Sketch


class Draw:
    """small utils to make it easier to
    draw points and lines in a sketch"""

    def __init__(self, sketch: "Sketch"):
        self.sketch = sketch
        self.x = 0.0
        self.y = 0.0
        self.point_added = False
        self.point_idx = 0
        self.points: list[Point] = []
        self.primitives: list[SketchPrimitiveTypes] = []

    def reset(self):
        self.x = 0.0
        self.y = 0.0
        self.point_added = False
        self.point_idx = 0
        self.points = []
        self.primitives = []

    def move_to(self, x: float, y: float):
        """Move to absolute position"""
        self.x = x
        self.y = y
        self.point_added = False

    def move(self, dx: float, dy: float):
        """Relative move"""
        self.x += dx
        self.y += dy
        self.point_added = False

    def add_point(self):
        if self.x == 0.0 and self.y == 0.0:
            point = self.sketch.origin
        else:
            point = Point(self.sketch, self.x, self.y)
        self.points.append(point)
        self.point_idx = len(self.points) - 1

    def line_to(self, x: float, y: float):
        if not self.point_added:
            self.add_point()
        self.x = x
        self.y = y
        self.add_point()
        self.point_added = True
        self.primitives.append(Line(self.points[-2], self.points[-1]))
        return

    def arc_to(self, x: float, y: float, radius: float):
        # TODO
        if not self.point_added:
            self.add_point()
        self.x = x
        self.y = y
        self.add_point()
        self.point_added = True
        self.primitives.append(
            Arc.from_two_points_and_radius(self.points[-2], self.points[-1], radius)
        )

    def line(self, dx: float, dy: float):
        if not self.point_added:
            self.add_point()
        self.x += dx
        self.y += dy
        self.add_point()
        self.point_added = True
        self.primitives.append(Line(self.points[-2], self.points[-1]))
        return

    def arc(self, dx: float, dy: float, radius: float):
        if not self.point_added:
            self.add_point()
        self.x += dx
        self.y += dy
        self.add_point()
        self.point_added = True
        self.primitives.append(
            Arc.from_two_points_and_radius(self.points[-2], self.points[-1], radius)
        )
        return

    def back_one_point(self):
        self.point_idx -= 1
        if self.point_idx < 0:
            self.point_idx = 0

    def get_closed_polygon(self) -> Polygon:
        # Deprecated use get_closed_shape.
        lines: List[Line] = []

        # Check that all the primitives are lines and filter them into a new list
        for primitive in self.primitives:
            if not isinstance(primitive, Line):
                raise InternalStateException("All primitives must be lines")
            lines.append(primitive)

        # for i in range(len(self.points) - 1):
        #     lines.append(Line(self.points[i], self.points[i + 1]))
        if self.points[0] != self.points[-1]:
            lines.append(Line(self.points[-1], self.points[0]))
        return Polygon(lines)

    def get_closed_shape(self) -> CustomClosedShape:
        """Return a closed shape using the primitives and closes it with a line if needed."""
        primitives = []
        for primitive in self.primitives:
            primitives.append(primitive)
        if self.points[0] != self.points[-1]:
            primitives.append(Line(self.points[-1], self.points[0]))
        return CustomClosedShape(primitives)

    def close(self) -> CustomClosedShape:
        return self.get_closed_shape()

    def close_with_mirror(self) -> CustomClosedShape:
        """Mirror the primitives to close the shape symmetrically based on axis from first to last point."""
        if len(self.points) < 2:
            raise GeometryException(
                "At least two points are required to perform mirroring."
            )

        # Determine the axis of symmetry
        start_point = self.points[0]
        end_point = self.points[-1]

        mirrored_primitives: list[SketchPrimitiveTypes] = []

        for primitive in self.primitives:
            mirrored_primitives.append(primitive.mirror(start_point, end_point))
        all_primitives = self.primitives + mirrored_primitives[::-1]

        return CustomClosedShape(all_primitives)

    def tangent_arc(self, dx: float, dy: float):
        """Draw an arc tangentially to the last primitive, relative move."""
        self.tangent_arc_to(self.x + dx, self.y + dy)

    def tangent_arc_to(self, x: float, y: float):
        """Draw an arc tangentially to the last primitive, ending at (x, y)."""
        if not self.point_added:
            self.add_point()

        p1 = self.points[-1]
        p2 = Point(self.sketch, x, y)
        if p1.x.value == p2.x.value and p1.y.value == p2.y.value:
            raise InvalidParameterValueException(
                "(x,y)", (x, y), "Destination point is the same as previous one"
            )

        tangent_unit_vector = self.primitives[-1].tangent()
        bisector_line = self._calculate_perpendicular_bisector(p1, p2)
        perpendicular_line_through_p1 = self._calculate_perpendicular_line(
            p1, tangent_unit_vector
        )

        center = Line.intersection(bisector_line, perpendicular_line_through_p1)

        # Ensure center is found
        if center is None:
            raise GeometryException("Cannot determine the center of the arc.")

            # Create an Arc using the three points on the arc: p1, a point on the arc, and p2
        # Calculate an intermediate point on the arc, halfway between p1 and p2
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

        midpoint = Point.midpoint(p1, p2)

        # Calculate the direction vector of the line p1 -> p2
        dx = p2.x.value - p1.x.value
        dy = p2.y.value - p1.y.value

        # Calculate the length of the direction vector
        length = math.sqrt(dx**2 + dy**2)  # cannot be zero
        if length == 0:
            raise InternalStateException("The length of the direction vector is zero")
        # Calculate the unit vector perpendicular to the direction vector
        unit_perpendicular = np.array([-dy / length, dx / length])

        # Create the perpendicular bisector line
        bisector_line = Line(
            midpoint, midpoint.translate(unit_perpendicular[0], unit_perpendicular[1])
        )

        return bisector_line

    def _calculate_perpendicular_line(
        self, point: Point, tangent_unit_vector: np.ndarray
    ) -> Line:
        """Calculate the line perpendicular to the tangent vector passing through the given point."""
        return Line(
            point, point.translate(-tangent_unit_vector[1], tangent_unit_vector[0])
        )

    def _update_state_after_arc(self, end_point: Point, arc: Arc):
        """Update the state after creating an arc."""
        self.x = end_point.x.value
        self.y = end_point.y.value
        self.points.append(end_point)
        self.primitives.append(arc)
        self.point_added = True

    def rounded_corner_then_line(self, dx: float, dy: float, radius: float):
        """Draw a rounded corner followed by a line, relative move."""
        self.rounded_corner_then_line_to(self.x + dx, self.y + dy, radius)

    def rounded_corner_then_line_to(self, x: float, y: float, radius: float):
        """Draw a rounded corner followed by a line, ending at (x, y)."""
        if not self.point_added:
            self.add_point()
        if len(self.primitives) == 0:
            raise GeometryException("No previous line to round the corner of.")
        last_primitive = self.primitives[-1]

        if not isinstance(last_primitive, Line):
            raise NotImplementedError("Rounded corners are only implemented for lines.")

        new_p2 = self._shorten_last_line(radius)
        self.primitives[-1] = Line(last_primitive.p1, new_p2)
        self.points[-1] = new_p2

        arc_end_point = self._calculate_arc_end_point(x, y, radius)

        self.x = new_p2.x.value
        self.y = new_p2.y.value
        self.tangent_arc_to(arc_end_point.x.value, arc_end_point.y.value)
        # check  if the arc_end_point is the same as the end point
        if self.x != x or self.y != y:
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
            raise GeometryException(
                "The radius is too large compared to the length of the previous line segment."
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
            raise GeometryException(
                "The radius is too large compared to the length of the new line segment, got radius: "
                + str(radius)
                + " and line length: "
                + str(new_line_length)
            )

        unit_dx = dx / new_line_length
        unit_dy = dy / new_line_length

        arc_end_x = self.x + radius * unit_dx
        arc_end_y = self.y + radius * unit_dy

        return Point(self.sketch, arc_end_x, arc_end_y)
