from __future__ import annotations

from cadbuildr.foundation.types.node import Node
import math
from cadbuildr.foundation.sketch.base import SketchElement
from cadbuildr.foundation.sketch.primitives.line import Line
from cadbuildr.foundation.sketch.point import Point
from cadbuildr.foundation.types.parameters import (
    UnCastFloat,
    cast_to_float_parameter,
    FloatParameter,
    StringParameter,
    cast_to_string_parameter,
    UnCastString,
)
from cadbuildr.foundation.types.node_children import NodeChildren
from cadbuildr.foundation.sketch.primitives import SketchPrimitiveTypes
from cadbuildr.foundation.exceptions import ElementsNotOnSameSketchException
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cadbuildr.foundation.sketch.sketch import Sketch


class ClosedSketchShape(SketchElement):
    """a closed shape is a shape that has a closed contour"""

    def get_points(self) -> list[Point]:
        """return the points of the shape"""
        raise NotImplementedError("Implement in children")


class CustomClosedShapeChildren(NodeChildren):
    primitives: list[SketchPrimitiveTypes]


class CustomClosedShape(ClosedSketchShape, Node):

    children_class = CustomClosedShapeChildren

    def __init__(self, primitives: list[SketchPrimitiveTypes]):
        for p in primitives[1:]:
            if primitives[0].sketch != p.sketch:
                raise ElementsNotOnSameSketchException(
                    f"Primitives {primitives[0]} and {p} are not on the same sketch"
                )
        sketch = primitives[0].sketch

        ClosedSketchShape.__init__(self, sketch)
        Node.__init__(self, parents=[sketch])

        self.children.set_primitives(primitives)

        self.primitives = primitives
        self.frame = sketch.frame
        self.params = {}

        # add to sketch
        sketch.add_element(self)

    def get_points(self) -> list[Point]:
        # combine all points from the primitives
        points: list = []
        for prim in self.primitives:
            points += prim.get_points()
        return points

    def rotate(self, angle: float, center: Point | None = None) -> "CustomClosedShape":
        if center is None:
            center = self.primitives[0].sketch.origin

        list_of_prim = [p.rotate(angle, center) for p in self.primitives]
        return CustomClosedShape(list_of_prim)

    def translate(self, dx: float, dy: float) -> "CustomClosedShape":
        list_of_prim = [p.translate(dx, dy) for p in self.primitives]
        return CustomClosedShape(list_of_prim)


CustomClosedShapeChildren.__annotations__["primitives"] = list[SketchPrimitiveTypes]


class PolygonChildren(NodeChildren):
    lines: list[Line]


class Polygon(ClosedSketchShape, Node):
    """type of closed shape made only of lines"""

    children_class = PolygonChildren

    def __init__(self, lines: list[Line]):
        for l in lines[1:]:
            if lines[0].sketch != l.sketch:
                raise ElementsNotOnSameSketchException(
                    f"Lines {lines[0]} and {l} are not on the same sketch"
                )
        sketch = lines[0].sketch

        # Check all frames are the same ?
        ClosedSketchShape.__init__(self, sketch)
        Node.__init__(self, parents=[sketch])

        self.children.set_lines(lines)

        self.lines = lines
        self.frame = sketch.frame
        self.params = {}

        # add to sketch
        sketch.add_element(self)

        # TODO make sure each line finish where the other one starts

    def check_if_closed(self):
        """Check if the shape is closed"""
        # We don't really care about this for now we don't use p2 of the
        # last line we just make a polygon with all the p1s.
        pass

    def get_points(self) -> list[Point]:
        """Get the first of each line"""
        return [line.p1 for line in self.lines]

    def rotate(self, angle: float, center: Point | None = None) -> "Polygon":
        if center is None:
            center = self.lines[0].sketch.origin
        lines = [l.rotate(angle, center) for l in self.lines]
        return Polygon(lines)

    def translate(self, dx: float, dy: float) -> "Polygon":
        lines = [l.translate(dx, dy) for l in self.lines]
        return Polygon(lines)

    @staticmethod
    def from_points(points: list[Point]) -> "Polygon":
        lines = []
        for i in range(len(points)):
            lines.append(Line(points[i], points[(i + 1) % len(points)]))
        return Polygon(lines)


PolygonChildren.__annotations__["lines"] = list[Line]


class CircleChildren(NodeChildren):
    center: Point
    radius: FloatParameter


class Circle(ClosedSketchShape, Node):
    children_class = CircleChildren

    def __init__(self, center: Point, radius: UnCastFloat):
        Node.__init__(self, [center.sketch])
        ClosedSketchShape.__init__(self, center.sketch)

        self.children.set_center(center)
        self.children.set_radius(cast_to_float_parameter(radius))

        # shortcuts
        self.center = self.children.center
        self.radius = self.children.radius

        # add to sketch
        center.sketch.add_element(self)

        self.params = {}

    def get_center(self) -> Point:
        """Get the first of each line"""
        return self.center

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


class EllipseChildren(NodeChildren):
    center: Point
    a: UnCastFloat
    b: UnCastFloat


class Ellipse(ClosedSketchShape, Node):
    children_class = EllipseChildren

    def __init__(self, center: Point, a: UnCastFloat, b: UnCastFloat):
        Node.__init__(self, [center.sketch])
        ClosedSketchShape.__init__(self, center.sketch)

        self.children.set_center(center)
        self.children.set_a(cast_to_float_parameter(a))
        self.children.set_b(cast_to_float_parameter(b))

        # shortcuts
        self.center = self.children.center
        self.a = self.children.a
        self.b = self.children.b

        # add to sketch
        center.sketch.add_element(self)

        self.params = {}

    # TODO check what is c1 and c2 bc not defined in __init__
    def get_focal_points(self):
        return self.c1, self.c2

    def rotate(self, angle: float, center: Point | None = None) -> "Ellipse":
        if center is None:
            center = self.center.get_frame().origin.point

        new_center = self.center.rotate(angle, center)
        return Ellipse(new_center, self.a, self.b)

    def translate(self, dx: float, dy: float) -> "Ellipse":
        new_center = self.center.translate(dx, dy)
        return Ellipse(new_center, self.a, self.b)


EllipseChildren.__annotations__["center"] = Point
EllipseChildren.__annotations__["a"] = FloatParameter
EllipseChildren.__annotations__["b"] = FloatParameter


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

        Polygon.__init__(self, lines)

    @staticmethod
    def from_center_and_side_length(center: Point, side_length: float) -> "Hexagon":
        radius = side_length / math.sqrt(3)
        # thanks copilot : https://www.wolframalpha.com/input/?i=side+length+of+hexagon+with+radius+1
        return Hexagon(center, radius)


class RoundedCornerPolygon(CustomClosedShape):
    def __init__(self, lines: list[Line], radius: float):
        # use pencil to draw rounded corners
        for l in lines[1:]:
            if lines[0].sketch != l.sketch:
                raise ElementsNotOnSameSketchException(
                    f"Lines {lines[0]} and {l} are not on the same sketch"
                )
        sketch = lines[0].sketch

        # move to the first point
        sketch.pencil.move_to(lines[0].p1.x.value, lines[0].p1.y.value)
        # move by radius on the first line
        [dx, dy] = lines[0].tangent()
        sketch.pencil.move(dx * radius, dy * radius)
        start_end_point = (sketch.pencil.x, sketch.pencil.y)
        sketch.pencil.line_to(lines[0].p2.x.value, lines[0].p2.y.value)

        for l in lines[1:]:
            # draw the line
            sketch.pencil.rounded_corner_then_line_to(
                l.p2.x.value, l.p2.y.value, radius
            )

        # close the shape
        sketch.pencil.rounded_corner_then_line_to(
            start_end_point[0], start_end_point[1], radius
        )

        #  pencil.close(self) -> CustomClosedShape:

        closed_shape = sketch.pencil.close()
        CustomClosedShape.__init__(self, closed_shape.primitives)


class SVGShapeChildren(NodeChildren):
    svg: StringParameter
    xshift: FloatParameter
    yshift: FloatParameter
    angle: FloatParameter
    scale: FloatParameter


class SVGShape(ClosedSketchShape, Node):
    """Use a SVG file given as a string to the constructor to create a shape in the sketch."""

    children_class = SVGShapeChildren

    def __init__(
        self,
        sketch: Sketch,
        svg: UnCastString,
        xshift: UnCastFloat = 0,
        yshift: UnCastFloat = 0,
        angle: UnCastFloat = 0,
        scale: UnCastFloat = 1,
    ):
        ClosedSketchShape.__init__(self, sketch)
        Node.__init__(self, parents=[sketch])

        self.children.set_svg(cast_to_string_parameter(svg))
        self.children.set_xshift(cast_to_float_parameter(xshift))
        self.children.set_yshift(cast_to_float_parameter(yshift))
        self.children.set_angle(cast_to_float_parameter(angle))
        self.children.set_scale(cast_to_float_parameter(scale))
        self.sketch = sketch
        self.params = {}

        # add to sketch
        sketch.add_element(self)


SVGShapeChildren.__annotations__["svg"] = StringParameter
SVGShapeChildren.__annotations__["xshift"] = FloatParameter
SVGShapeChildren.__annotations__["yshift"] = FloatParameter
SVGShapeChildren.__annotations__["angle"] = FloatParameter
SVGShapeChildren.__annotations__["scale"] = FloatParameter

ClosedSketchShapeTypes = Polygon | Circle | Ellipse | CustomClosedShape | SVGShape
