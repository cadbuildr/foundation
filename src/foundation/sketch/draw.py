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
