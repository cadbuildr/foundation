from foundation.types.node import Node
import math
from foundation.sketch.base import SketchShape
from foundation.sketch.primitives.line import Line
from foundation.sketch.point import Point
from foundation.types.parameters import (
    UnCastFloat,
    UnCastInt,
    cast_to_float_parameter,
    cast_to_int_parameter,
    FloatParameter,
    IntParameter,
)
from typing import TYPE_CHECKING
from foundation.types.node_children import NodeChildren
from foundation.sketch.primitives import SketchPrimitiveTypes

if TYPE_CHECKING:
    from foundation.sketch.sketch import Sketch


class ClosedSketchShape(SketchShape):
    """a closed shape is a shape that has a closed contour"""

    def get_points(self) -> list[Point]:
        """return the points of the shape"""
        raise NotImplementedError("Implement in children")


class CustomClosedSketchShapeChildren(NodeChildren):
    primitives: list[SketchPrimitiveTypes]


class CustomClosedSketchShape(ClosedSketchShape, Node):
    def __init__(self, primitives: list[SketchPrimitiveTypes]):
        sketch = primitives[0].sketch
        ClosedSketchShape.__init__(self, sketch)
        Node.__init__(self, parents=[sketch])

        self.children.set_primitives(primitives)
        self.primitives = primitives

    def get_points(self) -> list[Point]:
        # combine all points from the primitives
        points = []
        for prim in self.primitives:
            points += prim.get_points()
        return points

    def rotate(
        self, angle: float, center: Point | None = None
    ) -> "CustomClosedSketchShape":
        if center is None:
            center = self.primitives[0].sketch.origin
        list_of_prim = [p.rotate(angle, center) for p in self.primitives]
        return CustomClosedSketchShape(list_of_prim)

    def translate(self, dx: float, dy: float) -> "CustomClosedSketchShape":
        list_of_prim = [p.translate(dx, dy) for p in self.primitives]
        return CustomClosedSketchShape(list_of_prim)


class PolygonChildren(NodeChildren):
    lines: list[Line]


class Polygon(ClosedSketchShape, Node):
    """type of closed shape made only of lines"""

    children_class = PolygonChildren

    def __init__(self, sketch: "Sketch", lines: list[Line]):
        # Check all frames are the same ?
        ClosedSketchShape.__init__(self, lines[0].sketch)
        Node.__init__(self, parents=[sketch])

        self.children.set_lines(lines)

        self.frame = sketch.frame
        self.lines = lines
        self.params = {}

        # TODO make sure each line finish where the other one starts

    def check_if_closed(self):
        """Check if the shape is closed"""
        # We don't reall care about this for now we don't use p2 of the
        # last line we just make a polygon with all the p1s.
        pass

    def get_points(self) -> list[Point]:
        """Get the first of each line"""
        return [line.p1 for line in self.lines]

    def rotate(self, angle: float, center: Point | None = None) -> "Polygon":
        if center is None:
            center = self.lines[0].sketch.origin
        lines = [l.rotate(angle, center) for l in self.lines]
        return Polygon(self.sketch, lines)

    def translate(self, dx: float, dy: float) -> "Polygon":
        lines = [l.translate(dx, dy) for l in self.lines]
        return Polygon(self.sketch, lines)


PolygonChildren.__annotations__["lines"] = list[Line]


class CircleChildren(NodeChildren):
    center: Point
    radius: FloatParameter
    n_points: IntParameter


class Circle(ClosedSketchShape, Node):
    children_class = CircleChildren

    def __init__(self, center: Point, radius: UnCastFloat, n_points: UnCastInt = 20):
        Node.__init__(self, [center.sketch])
        ClosedSketchShape.__init__(self, center.sketch)

        self.children.set_center(center)
        self.children.set_radius(cast_to_float_parameter(radius))
        self.children.set_n_points(cast_to_int_parameter(n_points))

        # shortcuts
        self.center = self.children.center
        self.radius = self.children.radius
        self.n_points = self.children.n_points

        self.params = {}

    def get_center(self) -> Point:
        """Get the first of each line"""
        return self.center

    def get_points(self) -> list[Point]:
        """Get points along the circle"""
        return [
            Point(
                sketch=self.center.sketch,
                x=math.cos(2 * math.pi / self.n_points.value * i) * self.radius.value
                + self.center.x.value,
                y=math.sin(2 * math.pi / self.n_points.value * i) * self.radius.value
                + self.center.y.value,
            )
            for i in range(self.n_points.value)
        ]

    def rotate(self, angle: float, center: Point | None = None) -> "Circle":
        if center is None:
            center = self.center.sketch.origin

        new_center = self.center.rotate(angle, center)
        return Circle(new_center, self.radius)

    def translate(self, dx: float, dy: float) -> "Circle":
        new_center = self.center.translate(dx, dy)
        return Circle(new_center, self.radius)


CircleChildren.__annotations__["center"] = Point
CircleChildren.__annotations__["radius"] = FloatParameter
CircleChildren.__annotations__["n_points"] = IntParameter


class EllipseChildren(NodeChildren):
    center: Point
    a: UnCastFloat
    b: UnCastFloat
    n_points: UnCastInt


class Ellipse(ClosedSketchShape, Node):
    def __init__(
        self, center: Point, a: UnCastFloat, b: UnCastFloat, n_points: UnCastInt = 20
    ):
        Node.__init__(self, [center.sketch])
        ClosedSketchShape.__init__(self, center.sketch)

        self.children.set_center(center)
        self.children.set_a(cast_to_float_parameter(a))
        self.children.set_b(cast_to_float_parameter(b))
        self.children.set_n_points(cast_to_int_parameter(n_points))

        # shortcuts
        self.center = self.children.center
        self.a = self.children.a
        self.b = self.children.b
        self.n_points = self.children.n_points

        self.params = {}

    # TODO check what is c1 and c2 bc not defined in __init__
    def get_focal_points(self):
        return self.c1, self.c2

    def get_points(self) -> list[Point]:
        """Get Point along the eclipse"""
        return [
            Point(
                sketch=self.center.sketch,
                x=math.cos(2 * math.pi / self.n_points.value * i) * self.a.value
                + self.center.x.value,
                y=math.sin(2 * math.pi / self.n_points.value * i) * self.b.value
                + self.center.y.value,
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


class Hexagon(Polygon):
    def __init__(self, center: Point, radius: float):
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
    def from_center_and_side_length(center: Point, side_length: float) -> "Hexagon":
        radius = side_length / math.sqrt(3)
        # thanks copilot : https://www.wolframalpha.com/input/?i=side+length+of+hexagon+with+radius+1
        return Hexagon(center, radius)


ClosedSketchShapeTypes = Polygon | Circle | Ellipse | CustomClosedSketchShape
