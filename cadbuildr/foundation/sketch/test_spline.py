import numpy as np
import matplotlib.pyplot as plt
from cadbuildr.foundation import *
from cadbuildr.foundation.sketch.spline import (
    TwoPointsSpline,
    Spline,
    solve_at3_bt2_ct_d,
)
from cadbuildr.foundation.sketch.point import (
    PointWithTangent,
)  # TODO move to serizalizable_nodes


def utils_start():
    obj = Part()
    plane1 = obj.xy()
    s = Sketch(plane1)
    return s


def plot_spline(p1, p2, a1, a2):
    p1withT = PointWithTangent(p=p1, angle=a1)
    p2withT = PointWithTangent(p=p2, angle=a2)
    spline = TwoPointsSpline(p1withT, p2withT)
    points = spline.get_points(n_points=100)

    # plot
    plt.plot([p.x.value for p in points], [p.y.value for p in points])


def test_simple_aligned_spline():
    s = utils_start()
    p1 = Point(s, x=0, y=0)
    p2 = Point(s, x=1, y=1)
    a1 = np.pi / 4
    a2 = np.pi / 4
    plot_spline(p1, p2, a1, a2)


def test_spline_straight_up():
    s = utils_start()
    p1 = Point(s, x=1, y=1)
    p2 = Point(s, x=3, y=1)
    a1 = np.pi / 2
    a2 = np.pi / 2
    plot_spline(p1, p2, a1, a2)


def plot_big_spline(points_with_tangents):
    pts = Spline(points_with_tangents).get_points()
    plt.plot([p.x.value for p in pts], [p.y.value for p in pts])


def test_spline_big():
    s = utils_start()
    p1 = Point(s, x=0, y=0)
    p2 = Point(s, x=1, y=1)
    p3 = Point(s, x=3, y=1)
    p4 = Point(s, x=3, y=3)

    points_with_tangents = [
        PointWithTangent(p=p1, angle=np.pi / 2),
        PointWithTangent(p=p2, angle=np.pi / 2),
        PointWithTangent(p=p3, angle=np.pi / 2),
        PointWithTangent(p=p4, angle=np.pi / 2),
    ]
    plot_big_spline(points_with_tangents)


def test_solve_cubic_spline1d():
    (a, b, c, d) = solve_at3_bt2_ct_d(1, 3, 0.0, 0.0)

    def xt(t):
        return a * t**3 + b * t**2 + c * t + d

    assert xt(0) == 1
    assert xt(1) == 3


test_spline_big()
test_spline_straight_up()
