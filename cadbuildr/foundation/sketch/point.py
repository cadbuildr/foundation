from cadbuildr.foundation.types.parameters import (
    UnCastFloat,
    cast_to_float_parameter,
    FloatParameter,
)
from cadbuildr.foundation.types.node import Node
from cadbuildr.foundation.sketch.base import SketchElement

import numpy as np
import math
from cadbuildr.foundation.types.node_children import NodeChildren

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cadbuildr.foundation.sketch.sketch import Sketch


class PointChildren(NodeChildren):
    x: FloatParameter
    y: FloatParameter
    # name: StringParameter


class Point(SketchElement, Node):
    """A 2D Point in a sketch
    Could have many parents but needs a sketch as a parent.
    """

    parent_type = ["Sketch"]
    children_class = PointChildren

    def __init__(
        self,
        sketch: "Sketch",
        x: UnCastFloat,
        y: UnCastFloat,
    ):
        Node.__init__(self, [sketch])
        SketchElement.__init__(self, sketch)

        self.children.set_x(cast_to_float_parameter(x))
        self.children.set_y(cast_to_float_parameter(y))

        # shortcuts
        self.x = self.children.x
        self.y = self.children.y
        # self.name = self.children.name
        self.sketch = sketch

        # add to sketch
        sketch.add_element(self)

        self.params = {}

    def rotate(self, angle: float, center=None) -> "Point":
        """Make a new point by rotating this point around a center point
        angle in radians"""
        if center is None:
            center = self.sketch.origin.point

        dx = self.x.value - center.x.value
        dy = self.y.value - center.y.value

        new_point = Point(
            self.sketch,
            x=center.x.value + dx * math.cos(angle) - dy * math.sin(angle),
            y=center.y.value + dx * math.sin(angle) + dy * math.cos(angle),
        )
        return new_point

    def translate(self, dx: float, dy: float) -> "Point":
        """Make a new point by translating this point by a given distance"""
        return Point(self.sketch, self.x.value + dx, self.y.value + dy)

    def distance_to_other_point(self, p2: "Point") -> float:
        """Return the distance to another point"""
        return Point.distance_between_points(self, p2)

    def mirror(self, axis_start: "Point", axis_end: "Point") -> "Point":
        """Mirror the point over the line defined by two points"""
        dx = axis_end.x.value - axis_start.x.value
        dy = axis_end.y.value - axis_start.y.value
        a = (dx**2 - dy**2) / (dx**2 + dy**2)
        b = 2 * dx * dy / (dx**2 + dy**2)
        x = self.x.value
        y = self.y.value
        x_new = (
            a * (x - axis_start.x.value)
            + b * (y - axis_start.y.value)
            + axis_start.x.value
        )
        y_new = (
            b * (x - axis_start.x.value)
            - a * (y - axis_start.y.value)
            + axis_start.y.value
        )
        return Point(self.sketch, x_new, y_new)

    ## Shortcuts
    @staticmethod
    def midpoint(p1: "Point", p2: "Point") -> "Point":
        return Point(
            p1.sketch,
            (p1.x.value + p2.x.value) / 2,
            (p1.y.value + p2.y.value) / 2,
        )

    @staticmethod
    def distance_between_points(p1: "Point", p2: "Point") -> float:
        return np.sqrt((p1.x.value - p2.x.value) ** 2 + (p1.y.value - p2.y.value) ** 2)

    def __eq__(self, other):
        if not isinstance(other, Point):
            return False
        return self.x.value == other.x.value and self.y.value == other.y.value

    def __str__(self):
        return f"Point(x={self.x.value}, y={self.y.value})"


PointChildren.__annotations__["x"] = FloatParameter
PointChildren.__annotations__["y"] = FloatParameter


class PointWithTangentChildren(NodeChildren):
    p: Point
    angle: FloatParameter


class PointWithTangent(SketchElement, Node):
    children_class = PointWithTangentChildren

    def __init__(self, p: Point, angle: UnCastFloat):
        Node.__init__(self, [p.sketch])
        SketchElement.__init__(self, p.sketch)

        self.children.set_p(p)
        self.children.set_angle(cast_to_float_parameter(angle))

        # shortcuts
        self.p = self.children.p
        self.angle = self.children.angle

        # add to sketch
        p.sketch.add_element(self)

        self.params = {}


PointWithTangentChildren.__annotations__["p"] = Point
PointWithTangentChildren.__annotations__["angle"] = FloatParameter
