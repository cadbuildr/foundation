import math
from cadbuildr.foundation.sketch.point import Point, PointWithTangent
from cadbuildr.foundation.types.node import Node
from typing import List
from cadbuildr.foundation.types.node_children import NodeChildren
from cadbuildr.foundation.exceptions import ElementsNotOnSameSketchException


def solve_at3_bt2_ct_d(
    x0: float, x1: float, xp0: float, xp1: float
) -> tuple[float, float, float, float]:
    # solves q = a*t^3 + b*t^2 + c*t + d
    # q(0) = x0
    # q(1) = x1
    # q'(0) = xp0
    # q'(1) = xp1

    # for t = 0 :
    # d = x0
    # c = xp0
    # for t = 1:
    # 3a+2b+c = xp1
    # a+b+c+d = x1
    # => a = xp1 - 2*x1 + c + 2* d
    # => b = x1 - a - c -d
    # print(
    #     "Finding (a,b,c,d) for (x0,x1,xp0,xp1) = ({},{},{},{})".format(x0, x1, xp0, xp1)
    # )
    d = x0
    c = xp0
    a = xp1 - 2 * x1 + c + 2 * d
    b = x1 - a - c - d
    return (a, b, c, d)


class TwoPointsSpline:
    def __init__(self, p1: PointWithTangent, p2: PointWithTangent):
        if p1.p.sketch != p2.p.sketch:
            raise ElementsNotOnSameSketchException(
                f"Points {p1.p} and {p2.p} are not on the same sketch"
            )
        self.p1 = p1
        self.p2 = p2

    def get_xy_coeffs(
        self, smooth_factor: float | None = None
    ) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
        p1 = self.p1.p
        p2 = self.p2.p
        if smooth_factor is None:
            dx = p2.x.value - p1.x.value
            dy = p2.y.value - p1.y.value
            smooth_factor = max(abs(dx), abs(dy)) * 3.0

        def kx(angle: float) -> float:
            return smooth_factor * math.cos(angle)

        def ky(angle: float) -> float:
            return smooth_factor * math.sin(angle)

        x_coeffs = solve_at3_bt2_ct_d(
            p1.x.value, p2.x.value, kx(self.p1.angle.value), kx(self.p2.angle.value)
        )
        y_coeffs = solve_at3_bt2_ct_d(
            p1.y.value, p2.y.value, ky(self.p1.angle.value), ky(self.p2.angle.value)
        )
        return (x_coeffs, y_coeffs)

    def get_points(self, n_points: int) -> list[Point]:
        x_coeffs, y_coeffs = self.get_xy_coeffs()

        # now we can find the points
        points = []
        for i in range(n_points):
            t = i / n_points
            x = x_coeffs[0] * t**3 + x_coeffs[1] * t**2 + x_coeffs[2] * t + x_coeffs[3]
            y = y_coeffs[0] * t**3 + y_coeffs[1] * t**2 + y_coeffs[2] * t + y_coeffs[3]
            points.append(Point(self.p1.sketch, x, y))
        return points


class SplineChildren(NodeChildren):
    p_with_tangents: List[PointWithTangent]


class Spline(Node):
    parent_types = ["Sketch"]
    children_class = SplineChildren

    def __init__(self, points_with_tangent: list[PointWithTangent]):
        assert len(points_with_tangent) >= 2
        Node.__init__(self, [points_with_tangent[0].p.sketch])

        self.children.set_p_with_tangents(points_with_tangent)

        # shortcuts
        self.points_with_tangent = self.children.p_with_tangents

    def get_points(self, n_points: int | None = None) -> list[Point]:
        """Get Point along the spline, group points by 2 and then use the ThreePointSpline class to find the points"""
        if n_points is None:
            n_points = len(self.points_with_tangent) * 20
        points = []
        n_points_per_sub_spline = n_points // len(self.points_with_tangent)
        for i in range(0, len(self.points_with_tangent) - 1):
            points.extend(
                TwoPointsSpline(
                    self.points_with_tangent[i], self.points_with_tangent[i + 1]
                ).get_points(n_points_per_sub_spline)
            )

        return points


SplineChildren.__annotations__["p_with_tangents"] = List[PointWithTangent]
