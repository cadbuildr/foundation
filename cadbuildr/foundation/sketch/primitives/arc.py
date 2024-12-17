import math
from cadbuildr.foundation.sketch.point import Point
from cadbuildr.foundation.sketch.primitives.line import Line
from cadbuildr.foundation.types.node import Node
import numpy as np
from cadbuildr.foundation.types.parameters import UnCastFloat, cast_to_float_parameter
from cadbuildr.foundation.types.node_children import NodeChildren
from cadbuildr.foundation.exceptions import ElementsNotOnSameSketchException


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

        if p1.sketch != p2.sketch or p1.sketch != p3.sketch:
            raise ElementsNotOnSameSketchException(
                f"Points {p1}, {p2}, {p3} are not on the same sketch"
            )

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

    def is_counterclockwise(self) -> bool:
        """Check if the arc is counterclockwise based on the order of the points"""
        p1, p2, p3 = self.p1, self.p2, self.p3

        # Calculate the cross product of vectors (p2 - p1) and (p3 - p2)
        cross_product = (p2.x.value - p1.x.value) * (p3.y.value - p2.y.value) - (
            p2.y.value - p1.y.value
        ) * (p3.x.value - p2.x.value)
        return cross_product > 0

    def mirror(self, axis_start: Point, axis_end: Point) -> "Arc":
        """Mirror the arc over the line defined by two points"""

        if axis_start.sketch != self.sketch or axis_end.sketch != self.sketch:
            raise ElementsNotOnSameSketchException(
                f"Points {axis_start} and {axis_end} are not on the same sketch"
            )

        return Arc(
            self.p3.mirror(axis_start, axis_end),
            self.p2.mirror(axis_start, axis_end),
            self.p1.mirror(axis_start, axis_end),
        )

    @staticmethod
    def from_two_points_and_radius(p1: Point, p2: Point, radius: float) -> "Arc":
        """
        Create an arc from two points and a radius.
        The arc is on the left side of the line from p1 to p2.
        """

        if p1.sketch != p2.sketch:
            raise ElementsNotOnSameSketchException(
                f"Points {p1} and {p2} are not on the same sketch"
            )

        # Calculate midpoint
        midpoint = Point.midpoint(p1, p2)

        # Calculate distance between the points
        distance = Point.distance_between_points(p1, p2)

        if distance == 0:
            raise ValueError("The distance between the points is zero")

        if distance > 2 * math.fabs(radius):
            raise ValueError(
                "The distance between points is greater than the diameter of the circle",
                "distance: ",
                distance,
                "radius: ",
                radius,
            )

        # Calculate the direction perpendicular to the line segment
        dx = (p2.y.value - p1.y.value) / distance
        dy = -(p2.x.value - p1.x.value) / distance

        # Calculate the center of the circle
        # (p1, midpoint, center) is a right triangle
        # The distance from p1 to the center is the radius
        # The distance from p1 to the midpoint is half the distance between the points
        # hence the distance from the midpoint to the center is sqrt(radius^2 - (distance/2)^2)

        d = math.fabs(radius) - math.sqrt(radius**2 - (distance / 2) ** 2)

        sign = math.copysign(1, radius)

        # Determine the third point (assuming the arc is on the left side of the line)
        p3 = midpoint.translate(-d * dx * sign, -d * dy * sign)

        return Arc(p1, p3, p2)

    def tangent(self):
        """Tangent at p3"""
        center = self.get_center()
        dx = self.p3.x.value - center.x.value
        dy = self.p3.y.value - center.y.value
        # Calculate the tangent vector
        if self.is_counterclockwise():
            tangent_x = -dy  # Rotate the radius vector 90 degrees counterclockwise
            tangent_y = dx
        else:
            tangent_x = dy  # Rotate the radius vector 90 degrees clockwise
            tangent_y = -dx

        # normalize
        tangent_norm = np.linalg.norm([tangent_x, tangent_y])
        tangent_x /= tangent_norm
        tangent_y /= tangent_norm
        return tangent_x, tangent_y

    @staticmethod
    def from_point_with_tangent_and_point(tangent: Line, p2: Point):
        pass  # TODO

    def __str__(self) -> str:
        return f"Arc({self.p1}, {self.p2}, {self.p3})"

    def __repr__(self) -> str:
        return self.__str__()

    def get_center(self) -> Point:
        """Calculate the center of the circle passing through p1, p2, p3"""

        def perpendicular_bisector(p1: Point, p2: Point) -> tuple[float, float, float]:
            mid = Point.midpoint(p1, p2)
            dx = p2.x.value - p1.x.value
            dy = p2.y.value - p1.y.value
            if dy == 0:  # Vertical line case
                return (1, 0, -mid.x.value)
            slope = -dx / dy
            intercept = mid.y.value - slope * mid.x.value
            return (
                slope,
                -1,
                intercept,
            )  # line equation: slope * x - y + intercept = 0

        # Get the perpendicular bisectors of p1p2 and p2p3
        line1 = perpendicular_bisector(self.p1, self.p2)
        line2 = perpendicular_bisector(self.p2, self.p3)

        # Calculate the intersection of the two lines
        def intersection(
            line1: tuple[float, float, float], line2: tuple[float, float, float]
        ) -> Point:
            a1, b1, c1 = line1
            a2, b2, c2 = line2
            determinant = a1 * b2 - a2 * b1
            if determinant == 0:
                raise ValueError(
                    "The points are collinear and do not define a unique circle"
                )
            x = (b2 * c1 - b1 * c2) / determinant
            y = (a1 * c2 - a2 * c1) / determinant
            return Point(x=x, y=y, sketch=self.p1.sketch)

        return intersection(line1, line2)


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
