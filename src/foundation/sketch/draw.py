from foundation.sketch.point import Point
from foundation.sketch.line import Line
from foundation.sketch.sketch import Sketch
from foundation.sketch.closed_sketch_shape import Polygon


class Draw:
    """small utils to make it easier to
    draw points and lines in a sketch"""

    def __init__(self, sketch: Sketch):
        self.sketch = sketch
        self.x = 0.0
        self.y = 0.0
        self.point_added = False
        self.point_idx = 0
        self.points = []

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
        self.points.append(Point(self.sketch, self.x, self.y))
        self.point_idx = len(self.points) - 1

    def line_to(self, x: float, y: float):
        if not self.point_added:
            self.add_point()
        self.x = x
        self.y = y
        self.add_point()
        self.point_added = True
        return

    def line(self, dx: float, dy: float):
        if not self.point_added:
            self.add_point()
        self.x += dx
        self.y += dy
        self.add_point()
        self.point_added = True
        return

    def back_one_point(self):
        self.point_idx -= 1
        if self.point_idx < 0:
            self.point_idx = 0

    def get_closed_polygon(self) -> Polygon:
        lines = []
        for i in range(len(self.points) - 1):
            lines.append(Line(self.points[i], self.points[i + 1]))
        if self.points[0] != self.points[-1]:
            lines.append(Line(self.points[-1], self.points[0]))
        return Polygon(self.sketch, lines)
