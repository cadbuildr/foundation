import math
from foundation.sketch.point import Point
from foundation.sketch.primitives.line import Line
from foundation.types.node import Node
import numpy as np
from foundation.types.parameters import UnCastFloat, cast_to_float_parameter
from foundation.types.node_children import NodeChildren


def get_arc_center_from_3_points_coords(
    p1x: float, p1y: float, p2x: float, p2y: float, p3x: float, p3y: float
) -> tuple[float, float]:
    """
    Get the center of an arc from 3 points
    p1x, p1y, p2x, p2y, p3x, p3y"""

    A = np.array(
        [
            [p1x**2 + p1y**2, p1x, p1y, 1],
            [p2x**2 + p2y**2, p2x, p2y, 1],
            [p3x**2 + p3y**2, p3x, p3y, 1],
        ]
    )

    M11 = np.linalg.det(A[:, 1:4])
    if M11 == 0:
        raise ValueError("Points are aligned")

    M12 = np.linalg.det(A[np.ix_(range(3), [0, 2, 3])])
    M13 = np.linalg.det(A[np.ix_(range(3), [0, 1, 3])])

    x0 = 0.5 * M12 / M11
    y0 = -0.5 * M13 / M11

    return (x0, y0)


class ArcChildren(NodeChildren):
    p1: Point
    p2: Point
    p3: Point


class Arc(Node):  # TODO add SketchElement
    parent_types = ["Sketch"]
    children_class = ArcChildren

    def __init__(self, p1: Point, p2: Point, p3: Point):
        Node.__init__(self, parents=[p1.sketch])

        # TODO check if points are aligned and raise an error

        self.children.set_p1(p1)
        self.children.set_p2(p2)
        self.children.set_p3(p3)

        # shortcuts
        self.sketch = self.children.p1.sketch
        self.p1 = self.children.p1
        self.p2 = self.children.p2
        self.p3 = self.children.p3
        # adding to sketch
        self.sketch.add_element(self)

        # TODO update once we have a center calculation
        """ def calculate_radius(self) -> float: """
        """Calculate the radius of the arc"""
        """ return math.sqrt(
            (self.p1.x.value - self.center.x.value) ** 2
            + (self.p1.y.value - self.center.y.value) ** 2
        ) """

        """ def calculate_start_and_end_angles(self) -> tuple[float, float]: """
        """Calculate the start and end angles of the arc"""
        """ return math.atan2(
            self.p1.y.value - self.center.y.value, self.p1.x.value - self.center.x.value
        ), math.atan2(
            self.p2.y.value - self.center.y.value, self.p2.x.value - self.center.x.value
        ) """

    def rotate(self, angle: float, center: Point) -> "Arc":
        """Rotate the arc"""
        new_arc = Arc(
            self.p1.rotate(angle, center),
            self.p2.rotate(angle, center),
            self.p3.rotate(angle, center),
        )
        return new_arc

    def translate(self, dx: float, dy: float) -> "Arc":
        """Translate the arc"""
        new_arc = Arc(
            self.p1.translate(dx, dy),
            self.p2.translate(dx, dy),
            self.p3.translate(dx, dy),
        )
        return new_arc

    def get_points(self):
        return [self.p1, self.p2, self.p3]

    @staticmethod
    def from_two_points_and_radius(p1: Point, p2: Point, radius: float) -> "Arc":
        """
        Create an arc from two points and a radius
        """
        # TODO test this function
        midpoint = Point(
            p1.sketch, (p1.x.value + p2.x.value) / 2, (p1.y.value + p2.y.value) / 2
        )

        distance = math.sqrt(
            (midpoint.x.value - p1.x.value) ** 2 + (midpoint.y.value - p1.y.value) ** 2
        )

        if distance > radius:
            raise ValueError("Points are too far from the midpoint")

        p3 = Point(
            p1.sketch,
            midpoint.x.value + math.sqrt(radius**2 - distance**2),
            midpoint.y.value,
        )

        return Arc(p1, p3, p2)

    @staticmethod
    def from_point_with_tangent_and_point(tangent: Line, p2: Point):
        pass  # TODO


ArcChildren.__annotations__["p1"] = Point
ArcChildren.__annotations__["p2"] = Point
ArcChildren.__annotations__["p3"] = Point


class EllipseArc(Node):
    parent_types = ["Sketch"]

    def __init__(
        self,
        center: Point,
        a: UnCastFloat,
        b: UnCastFloat,
        angle1: UnCastFloat,  # start angle
        angle2: UnCastFloat,  # end angle
    ):
        Node.__init__(self, parents=[center.sketch])
        self.center = center
        self.a = cast_to_float_parameter(a)
        self.b = cast_to_float_parameter(b)
        self.s_angle = cast_to_float_parameter(angle1)
        self.end_angle = cast_to_float_parameter(angle2)
        self.sketch = center.sketch
        # adding to sketch
        self.sketch.add_element(self)

    def get_points(self, n_points: int = 20) -> list[Point]:
        """Get Point along the eclipse"""
        angles = [
            self.s_angle + (self.end_angle.value - self.s_angle.value) * i / n_points
            for i in range(n_points + 1)
        ]
        return [
            Point(
                sketch=self.center.sketch,
                x=math.cos(angle) * self.a.value + self.center.x.value,
                y=math.sin(angle) * self.b.value + self.center.y.value,
            )
            for angle in angles
        ]

    # TODO test EllipseArc rotation and translation
    def rotate(self, angle: float, center: Point | None = None) -> "EllipseArc":
        """Rotate the arc"""
        if center is None:
            center = self.center.sketch.origin
        new_arc = EllipseArc(
            center.rotate(angle, center),
            self.a,
            self.b,
            self.s_angle.value + angle,
            self.end_angle.value + angle,
        )
        return new_arc

    def translate(self, dx: float, dy: float) -> "EllipseArc":
        """Translate the arc"""
        new_arc = EllipseArc(
            self.center.translate(dx, dy),
            self.a,
            self.b,
            self.s_angle,
            self.end_angle,
        )
        return new_arc
