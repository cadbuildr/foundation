from foundation.types.node import Node
from foundation.sketch.base import SketchElement
from foundation.sketch.point import Point
from foundation.types.node_children import NodeChildren

import numpy as np
import math
import typing


def triangle_area(p1: Point, p2: Point, p3: Point, absolute: bool = True) -> float:
    """Area of a triangle given 3 points"""

    mat = np.array(
        [
            [p1.x.value, p1.y.value, 1],
            [p2.x.value, p2.y.value, 1],
            [p3.x.value, p3.y.value, 1],
        ]
    )
    area = 0.5 * np.linalg.det(mat)
    if absolute:
        return abs(area)
    else:
        return area


class LineChildren(NodeChildren):
    p1: Point
    p2: Point


class Line(SketchElement, Node):
    """Class for a 2D line in a sketch
    Could have many parents (like polygons ...)
    but needs a sketch for a parent as well.
    """

    parent_types = ["Sketch"]
    children_class = LineChildren

    def __init__(self, p1: Point, p2: Point):
        # geometry.Line.__init__(self, p1, p2)
        Node.__init__(self, [p1.sketch])
        if p1.sketch != p2.sketch:
            raise ValueError("Points are not on the same sketch")
        SketchElement.__init__(self, p1.sketch)

        self.children.set_p1(p1)
        self.children.set_p2(p2)

        # shortcuts
        self.p1 = self.children.p1
        self.p2 = self.children.p2

        self.params = {}

    def rotate(self, angle: float, center: Point | None = None) -> "Line":
        if center is None:
            center = self.p1.frame.origin.point

        p1 = self.p1.rotate(angle, center)
        p2 = self.p2.rotate(angle, center)
        return Line(p1, p2)

    def translate(self, dx: float, dy: float) -> "Line":
        return Line(self.p1.translate(dx, dy), self.p2.translate(dx, dy))

    def dx(self):
        return self.params[2].value - self.params[0].value

    def dy(self):
        return self.params[3].value - self.params[1].value

    def length(self) -> float:
        return self.p1.distance_to_other_point(self.p2)

    def angle_to_other_line(self, line_b: "Line") -> float:
        """Return the angle in degrees to another line.
        TODO this should probablly return a FloatParameter with a parent being the line
        so that we actually propgate the changes in the tree.
        """
        return (
            math.degrees(
                math.atan2(line_b.dy(), line_b.dx()) - math.atan2(self.dy(), self.dx())
            )
            % 360
        )

    def distance_to_point(self, p1: Point, absolute: bool = True) -> float:
        """
        Same here, probably should return a FloatParameter
        area is bxh/2"""
        return (
            triangle_area(p1, self.p1, self.p2, absolute=absolute) * 2.0 / self.length()
        )

    def line_equation(self) -> typing.Callable[[float, float], float]:
        """return equation left side as ax + by + c = 0
        one solution is a = dy, b = -dx, c = y1x2-x1y2

        """

        def equation(x: float, y: float) -> float:
            return (
                self.dy() * x
                - self.dx() * y
                + self.p1.y.value * self.p2.x.value
                - self.p1.x.value * self.p2.y.value
            )

        return equation

    def closest_point_on_line(self, p0: Point) -> tuple[float, float]:
        """
        :param p0: Point
        project point on line,
        """
        # unit vector
        u = np.array([self.dx(), self.dy()])
        u = u / np.linalg.norm(u)
        # vector p1 to p0
        v = np.array([p0.x.value - self.p1.x.value, p0.y.value - self.p1.y.value])
        p_proj = np.dot(u, v) * u + np.array([self.p1.x.value, self.p1.y.value])
        return p_proj[0], p_proj[1]

    def get_points(self):
        return [self.p1, self.p2]
