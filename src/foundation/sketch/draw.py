from foundation.sketch.point import Point
from foundation.sketch.primitives.line import Line
from foundation.sketch.primitives.arc import Arc
from foundation.sketch.closed_sketch_shape import (
    Polygon,
    CustomClosedSketchShape,
    SketchPrimitiveTypes,
)

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from foundation.sketch.sketch import Sketch


def mirror_point(point: Point, axis_start: Point, axis_end: Point):
    """Mirrors a point across the axis defined by axis_start and axis_end."""
    dx = axis_end.x.value - axis_start.x.value
    dy = axis_end.y.value - axis_start.y.value
    a = (dx**2 - dy**2) / (dx**2 + dy**2)
    b = 2 * dx * dy / (dx**2 + dy**2)
    x = point.x.value
    y = point.y.value
    x_new = (
        a * (x - axis_start.x.value) + b * (y - axis_start.y.value) + axis_start.x.value
    )
    y_new = (
        b * (x - axis_start.x.value) - a * (y - axis_start.y.value) + axis_start.y.value
    )
    return Point(point.sketch, x_new, y_new)


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
                raise ValueError("All primitives must be lines")
            lines.append(primitive)

        # for i in range(len(self.points) - 1):
        #     lines.append(Line(self.points[i], self.points[i + 1]))
        if self.points[0] != self.points[-1]:
            lines.append(Line(self.points[-1], self.points[0]))
        return Polygon(self.sketch, lines)

    def get_closed_shape(self) -> CustomClosedSketchShape:
        """Return a closed shape using the primitives and closes it with a line if needed."""
        primitives = []
        for primitive in self.primitives:
            primitives.append(primitive)
        if self.points[0] != self.points[-1]:
            primitives.append(Line(self.points[-1], self.points[0]))
        return CustomClosedSketchShape(self.sketch, primitives)

    def close(self) -> CustomClosedSketchShape:
        return self.get_closed_shape()

    def close_with_mirror(self) -> CustomClosedSketchShape:
        """Mirror the primitives to close the shape symmetrically based on axis from first to last point."""
        if len(self.points) < 2:
            raise ValueError("At least two points are required to perform mirroring.")

        # Determine the axis of symmetry
        start_point = self.points[0]
        end_point = self.points[-1]

        mirrored_primitives: list[SketchPrimitiveTypes] = []

        for primitive in self.primitives:
            if isinstance(primitive, Line):
                start = mirror_point(primitive.p1, start_point, end_point)
                end = mirror_point(primitive.p2, start_point, end_point)
                mirrored_primitives.append(Line(end, start))
            elif isinstance(primitive, Arc):
                mp1 = mirror_point(primitive.p1, start_point, end_point)
                mp2 = mirror_point(primitive.p2, start_point, end_point)
                mp3 = mirror_point(primitive.p3, start_point, end_point)
                mirrored_primitives.append(Arc(mp3, mp2, mp1))
            else:
                raise ValueError("Unsupported primitive type for mirroring.")

        all_primitives = self.primitives + mirrored_primitives[::-1]

        return CustomClosedSketchShape(self.sketch, all_primitives)
