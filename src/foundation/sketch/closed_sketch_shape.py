from foundation.types.node import Node
import math
from foundation.sketch.base import SketchShape

from foundation.sketch.line import Line
from foundation.sketch.point import Point
from foundation.sketch.sketch import Sketch
from foundation.types.parameters import (
    UnCastFloat,
    UnCastInt,
    cast_to_float_parameter,
    cast_to_int_parameter,
)


class ClosedSketchShape(SketchShape):
    """a closed shape is a shape that has a closed contour"""

    def get_points(self) -> list[Point]:
        """return the points of the shape"""
        raise NotImplementedError("Implement in children")


class CustomClosedSketchShape(ClosedSketchShape, Node):
    def __init__(self, list_of_prim: list[Node]):
        self.list_of_prim = list_of_prim
        ClosedSketchShape.__init__(self, list_of_prim[0].sketch)
        Node.__init__(self, parents=[list_of_prim[0].sketch])
        for l in list_of_prim:
            self.register_child(l)

    def get_points(self) -> list[Point]:
        # combine all points from the primitives
        points = []
        for prim in self.list_of_prim:
            points += prim.get_points()
        return points

    def rotate(
        self, angle: float, center: Point | None = None
    ) -> "CustomClosedSketchShape":
        if center is None:
            center = self.list_of_prim[0].get_frame().origin.point
        list_of_prim = [p.rotate(angle, center) for p in self.list_of_prim]
        return CustomClosedSketchShape(list_of_prim)

    def translate(self, dx: float, dy: float) -> "CustomClosedSketchShape":
        list_of_prim = [p.translate(dx, dy) for p in self.list_of_prim]
        return CustomClosedSketchShape(list_of_prim)


class Polygon(ClosedSketchShape, Node):
    """type of closed shape made only of lines"""

    def __init__(self, sketch: Sketch, lines: list[Line]):
        # Check all frames are the same ?
        ClosedSketchShape.__init__(self, lines[0].sketch)
        Node.__init__(self, parents=[sketch])
        self.frame = sketch.frame
        self.lines = lines
        for l in lines:
            self.register_child(l)
        self.params = {"n_lines": [l.id for l in lines]}

        # TODO make sure each line finish where the other one starts

    def check_if_closed(self):
        """Check if the shape is closed"""
        # TODO
        pass

    def get_points(self) -> list[Point]:
        """Get the first of each line"""
        return [line.p1 for line in self.lines]

    def rotate(self, angle: float, center: Point | None = None) -> "Polygon":
        if center is None:
            center = self.lines[0].get_frame().origin
        lines = [l.rotate(angle, center) for l in self.lines]
        return Polygon(self.sketch, lines)

    def translate(self, dx: float, dy: float) -> "Polygon":
        lines = [l.translate(dx, dy) for l in self.lines]
        return Polygon(self.sketch, lines)


class Circle(ClosedSketchShape, Node):
    def __init__(self, center: Point, radius: UnCastFloat, n_points: UnCastInt = 20):
        Node.__init__(self, [center.sketch])
        ClosedSketchShape.__init__(self, center.sketch)
        self.center = center
        self.radius = cast_to_float_parameter(radius)
        self.n_points = cast_to_int_parameter(n_points)
        self.register_child(center)
        self.register_child(self.radius)
        self.register_child(self.n_points)

        self.params = {
            "n_center": center.id,
            "n_radius": self.radius.id,
            "n_points": self.n_points.id,
        }

    def get_center(self) -> Point:
        """Get the first of each line"""
        return self.center

    def get_points(self) -> list[Point]:
        """Get points along the circle"""
        return [
            Point(
                x=math.cos(2 * math.pi / self.n_points.value * i) * self.radius.value
                + self.center.x.value,
                y=math.sin(2 * math.pi / self.n_points.value * i) * self.radius.value
                + self.center.y.value,
                frame=self.center.parents[0],
            )
            for i in range(self.n_points.value)
        ]

    def rotate(self, angle: float, center: Point | None = None) -> "Circle":
        if center is None:
            center = self.center.get_frame().origin.point

        new_center = self.center.rotate(angle, center)
        return Circle(new_center, self.radius)

    def translate(self, dx: float, dy: float) -> "Circle":
        new_center = self.center.translate(dx, dy)
        return Circle(new_center, self.radius)


class Ellipse(ClosedSketchShape, Node):
    def __init__(
        self, center: Point, a: UnCastFloat, b: UnCastFloat, n_points: UnCastInt = 20
    ):
        Node.__init__(self, [center.sketch])
        ClosedSketchShape.__init__(self, center.sketch)

        self.a = cast_to_float_parameter(a)
        self.b = cast_to_float_parameter(b)
        self.center = center
        self.n_points = cast_to_int_parameter(n_points)

        self.register_child(center)
        self.register_child(self.a)
        self.register_child(self.b)
        self.register_child(self.n_points)
        self.params = {
            "n_center": center.id,
            "n_a": self.a.id,
            "n_b": self.b.id,
            "n_points": self.n_points.id,
        }

    # TODO check what is c1 and c2 bc not defined in __init__
    def get_focal_points(self):
        return self.c1, self.c2

    # TODO check if i use list of typing or list
    # https://stackoverflow.com/questions/39458193/using-list-tuple-etc-from-typing-vs-directly-referring-type-as-list-tuple-etc
    def get_points(self) -> list[Point]:
        """Get Point along the eclipse"""
        return [
            Point(
                x=math.cos(2 * math.pi / self.n_points.value * i) * self.a.value
                + self.center.x.value,
                y=math.sin(2 * math.pi / self.n_points.value * i) * self.b.value
                + self.center.y.value,
                frame=self.center.parents[0],
            )
            for i in range(self.n_points.value)
        ]

    def rotate(self, angle: float, center: Point | None = None) -> "Ellipse":
        if center is None:
            center = self.center.get_frame().origin.point

        new_center = self.center.rotate(angle, center)
        return Ellipse(new_center, self.a, self.b)

    def translate(self, dx: float, dy: float) -> "Ellipse":
        new_center = self.center.translate(dx, dy)
        return Ellipse(new_center, self.a, self.b)


# TODO make it a Node
class Hexagon(Polygon):
    # TODO check if center is a point and radius a float and type methods
    def __init__(self, center, radius):
        # TODO : make sure the center is in the sketch
        # TODO : make sure the radius is in the sketch
        lines = []
        points = []
        self.sketch = center.sketch
        self.radius = radius

        # create points
        for i in range(6):
            points.append(
                Point(
                    center.sketch,
                    x=math.cos(2 * math.pi / 6 * i) * self.radius + center.x.value,
                    y=math.sin(2 * math.pi / 6 * i) * self.radius + center.y.value,
                )
            )

        # create lines
        for i in range(6):
            lines.append(Line(points[i], points[(i + 1) % 6]))

        Polygon.__init__(self, self.sketch, lines)

    @staticmethod
    def from_center_and_side_length(center, side_length):
        radius = side_length / math.sqrt(3)
        # thanks copilot : https://www.wolframalpha.com/input/?i=side+length+of+hexagon+with+radius+1
        return Hexagon(center, radius)
