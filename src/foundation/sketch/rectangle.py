import math
from foundation.sketch.line import Line
from foundation.sketch.point import Point
from foundation.sketch.closed_sketch_shape import Polygon


class Rectangle(Polygon):
    def __init__(self, sketch, p1, p2, p3, p4):
        lines = [Line(p1, p2), Line(p2, p3), Line(p3, p4), Line(p4, p1)]
        Polygon.__init__(self, sketch, lines)

    @staticmethod
    def from_2_points(p1: Point, p3: Point):
        """Create a rectangle from 2 points assuming they are on the
        diagonal of the rectangle and that the side of the rectangle
        are parallel to the x and y axis"""
        sketch = p1.sketch
        p2 = Point(sketch, p3.x.value, p1.y.value)
        p4 = Point(sketch, p1.x.value, p3.y.value)

        return Rectangle(sketch, p1, p4, p3, p2)

    def rotate(self, angle, center=None):
        if center is None:
            center = self.lines[0].p1.point
        lines = [l.rotate(angle, center) for l in self.lines]
        return Rectangle(self.sketch, *lines)

    def translate(self, dx, dy):
        lines = [l.translate(dx, dy) for l in self.lines]
        return Rectangle(self.sketch, *lines)

    @staticmethod
    def from_center_and_point(center: Point, p1: Point):
        """Create a rectangle from a center point and a point"""
        sketch = center.sketch
        dx = center.x.value - p1.x.value
        dy = center.y.value - p1.y.value

        p2 = Point(sketch, p1.x.value, p1.y.value + dy * 2)

        p3 = Point(sketch, p1.x.value + dx * 2, p1.y.value + dy * 2)

        p4 = Point(sketch, p1.x.value + dx * 2, p1.y.value)

        return Rectangle(sketch, p1, p2, p3, p4)

    @staticmethod
    def from_3_points(p1: Point, p2: Point, opposed: Point):
        """create a rectangle using one side as [p1, p2] and the opposite side going through opposed"""
        sketch = p1.sketch
        l1 = Line(p1, p2)

        width = l1.distance_to_point(opposed, abs=False)
        # angle between x axis and [p1, p2]
        angle = math.atan2(l1.dy(), l1.dx())

        # calculate p3
        p3 = Point(
            sketch,
            p2.x.value + width * math.cos(angle),
            p2.y.value + width * math.sin(angle),
        )
        p4 = Point(
            sketch,
            p1.x.value + width * math.cos(angle),
            p1.y.value + width * math.sin(angle),
        )

        return Rectangle(sketch, p1, p2, p3, p4)

    @staticmethod
    def from_center_and_sides(center: Point, side1, side2):
        """Create a rectangle from a center point and 2 sides"""
        sketch = center.sketch
        p1 = Point(sketch, center.x.value - side1 / 2, center.y.value - side2 / 2)
        p4 = Point(sketch, center.x.value - side1 / 2, center.y.value + side2 / 2)
        p3 = Point(sketch, center.x.value + side1 / 2, center.y.value + side2 / 2)
        p2 = Point(sketch, center.x.value + side1 / 2, center.y.value - side2 / 2)

        return Rectangle(sketch, p1, p2, p3, p4)


class Square(Rectangle):
    """A square is a polygon with 4 lines"""

    def __init__(self, sketch, p1, p2, p3, p4):
        lines = [Line(p1, p2), Line(p2, p3), Line(p3, p4), Line(p4, p1)]
        Polygon.__init__(self, sketch, lines)

    @staticmethod
    def from_center_and_side(center, side):
        """Create a square from a center point and a side"""
        sketch = center.sketch
        p1 = Point(center.sketch, center.x.value - side / 2, center.y.value - side / 2)
        p2 = Point(center.sketch, center.x.value + side / 2, center.y.value - side / 2)
        p3 = Point(center.sketch, center.x.value + side / 2, center.y.value + side / 2)
        p4 = Point(center.sketch, center.x.value - side / 2, center.y.value + side / 2)
        return Square(sketch, p1, p2, p3, p4)
