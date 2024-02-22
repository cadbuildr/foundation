from foundation.types.parameters import (
    UnCastFloat,
    UnCastBool,
    UnCastString,
    cast_to_float_parameter,
    cast_to_bool_parameter,
    cast_to_string_parameter,
)
from foundation.types.node import Node
from foundation.sketch.base import SketchShape

from typing import TYPE_CHECKING
import numpy as np
import math

if TYPE_CHECKING:
    from foundation.sketch.sketch import Sketch


class Point(SketchShape, Node):
    """A 2D Point in a sketch
    Could have many parents but needs a sketch as a parent.
    """

    parent_type = ["Sketch"]

    def __init__(
        self,
        sketch: "Sketch",
        x: UnCastFloat,
        y: UnCastFloat,
        anchor: UnCastBool = False,
        name: UnCastString | None = None,
    ):
        self.x = cast_to_float_parameter(x)
        self.y = cast_to_float_parameter(y)
        self.anchor = cast_to_bool_parameter(anchor)

        Node.__init__(self, [sketch])
        SketchShape.__init__(self, sketch)
        self.x.attach_to_parent(self)
        self.y.attach_to_parent(self)
        self.anchor.attach_to_parent(self)
        if name is None:
            name = "p_" + str(self.id)
        self.name = cast_to_string_parameter(name)
        self.name.attach_to_parent(self)

        self.params = {
            # n_ because they are nodes.
            "n_x": self.x.id,
            "n_y": self.y.id,
            "n_anchor": self.anchor.id,
            "n_name": self.name.id,
        }

    def rotate(self, angle, center=None):
        """Make a new point by rotating this point around a center point
        angle in radians"""
        if center is None:
            center = self.frame.origin.point

        dx = self.x.value - center.x.value
        dy = self.y.value - center.y.value

        new_point = Point(
            self.sketch,
            x=center.x.value + dx * math.cos(angle) - dy * math.sin(angle),
            y=center.y.value + dx * math.sin(angle) + dy * math.cos(angle),
        )
        return new_point

    def translate(self, dx, dy):
        """Make a new point by translating this point by a given distance"""
        return Point(self.sketch, self.x + dx, self.y + dy)

    def distance_to_other_point(self, p2):
        return np.sqrt(
            (self.x.value - p2.x.value) ** 2 + (self.y.value - p2.y.value) ** 2
        )


class PointWithTangent(SketchShape, Node):
    def __init__(self, p: Point, angle: UnCastFloat):
        self.p = p
        self.angle = cast_to_float_parameter(angle)
        Node.__init__(self, [p.sketch])
        SketchShape.__init__(self, p.sketch)
        self.angle.attach_to_parent(self)
        self.params = {
            "n_p": p.id,
            "n_angle": self.angle.id,
        }
