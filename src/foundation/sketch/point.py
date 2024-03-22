from foundation.types.parameters import (
    UnCastFloat,
    UnCastBool,
    UnCastString,
    cast_to_float_parameter,
    cast_to_bool_parameter,
    cast_to_string_parameter,
    FloatParameter,
    BoolParameter,
    StringParameter,
)
from foundation.types.node import Node
from foundation.sketch.base import SketchShape

import numpy as np
import math
from foundation.types.node_children import NodeChildren

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from foundation.sketch.sketch import Sketch


class PointChildren(NodeChildren):
    x: FloatParameter
    y: FloatParameter
    anchor: BoolParameter
    name: StringParameter


class Point(SketchShape, Node):
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
        anchor: UnCastBool = False,
        name: UnCastString | None = None,
    ):
        Node.__init__(self, [sketch])
        SketchShape.__init__(self, sketch)

        self.children.set_x(cast_to_float_parameter(x))
        self.children.set_y(cast_to_float_parameter(y))
        self.children.set_anchor(cast_to_bool_parameter(anchor))
        if name is None:
            name = "p_" + str(self.id)
        self.children.set_name(cast_to_string_parameter(name))

        # shortcuts
        self.x = self.children.x
        self.y = self.children.y
        self.anchor = self.children.anchor
        self.name = self.children.name
        self.sketch = sketch

        self.params = {
            # n_ because they are nodes.
            "n_x": self.x.id,
            "n_y": self.y.id,
            "n_anchor": self.anchor.id,
            "n_name": self.name.id,
        }

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
        return np.sqrt(
            (self.x.value - p2.x.value) ** 2 + (self.y.value - p2.y.value) ** 2
        )


PointChildren.__annotations__["x"] = FloatParameter
PointChildren.__annotations__["y"] = FloatParameter
PointChildren.__annotations__["anchor"] = BoolParameter
PointChildren.__annotations__["name"] = StringParameter


class PointWithTangentChildren(NodeChildren):
    p: Point
    angle: FloatParameter


class PointWithTangent(SketchShape, Node):
    children_class = PointWithTangentChildren

    def __init__(self, p: Point, angle: UnCastFloat):
        Node.__init__(self, [p.sketch])
        SketchShape.__init__(self, p.sketch)

        self.children.set_p(p)
        self.children.set_angle(cast_to_float_parameter(angle))

        # shortcuts
        self.p = self.children.p
        self.angle = self.children.angle

        self.params = {
            "n_p": p.id,
            "n_angle": self.angle.id,
        }


PointWithTangentChildren.__annotations__["p"] = Point
PointWithTangentChildren.__annotations__["angle"] = FloatParameter
