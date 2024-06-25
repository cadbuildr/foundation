import unittest
from foundation import Point, Sketch, start_component
from foundation.sketch.draw import mirror_point, Draw
from foundation.sketch.point import Point
from foundation.sketch.primitives.line import Line
from foundation.sketch.primitives.arc import Arc
from foundation.sketch.sketch import Sketch
import numpy as np


class TestMirrorPoint(unittest.TestCase):

    def setUp(self):
        self.part = start_component()
        self.sketch = Sketch(self.part.xy())

    def test_mirror_point_across_x_axis(self):
        point = Point(self.sketch, 2.0, 3.0)
        axis_start = Point(self.sketch, 0.0, 0.0)
        axis_end = Point(self.sketch, 1.0, 0.0)
        mirrored_point = mirror_point(point, axis_start, axis_end)
        self.assertAlmostEqual(mirrored_point.x.value, 2.0)
        self.assertAlmostEqual(mirrored_point.y.value, -3.0)

    def test_mirror_point_across_y_axis(self):
        point = Point(self.sketch, 3.0, 2.0)
        axis_start = Point(self.sketch, 0.0, 0.0)
        axis_end = Point(self.sketch, 0.0, 1.0)
        mirrored_point = mirror_point(point, axis_start, axis_end)
        self.assertAlmostEqual(mirrored_point.x.value, -3.0)
        self.assertAlmostEqual(mirrored_point.y.value, 2.0)

    def test_mirror_point_across_diagonal_axis(self):
        point = Point(self.sketch, 1.0, 2.0)
        axis_start = Point(self.sketch, 0.0, 0.0)
        axis_end = Point(self.sketch, 1.0, 1.0)
        mirrored_point = mirror_point(point, axis_start, axis_end)
        self.assertAlmostEqual(mirrored_point.x.value, 2.0)
        self.assertAlmostEqual(mirrored_point.y.value, 1.0)


class TestDraw(unittest.TestCase):

    def setUp(self):
        self.part = start_component()
        self.sketch = Sketch(self.part.xy())
        self.sketch.pencil.line(20, 0)

    def test_calculate_perpendicular_line(self):
        point = Point(self.sketch, 1, 1)
        tangent_unit_vector = np.array([1 / np.sqrt(2), 1 / np.sqrt(2)])
        perpendicular_line = self.sketch.pencil._calculate_perpendicular_line(
            point, tangent_unit_vector
        )
        expected_point = point.translate(-1 / np.sqrt(2), 1 / np.sqrt(2))
        self.assertAlmostEqual(perpendicular_line.p2.x.value, expected_point.x.value)
        self.assertAlmostEqual(perpendicular_line.p2.y.value, expected_point.y.value)

    def test_tangent_arc_to(self):
        self.sketch.pencil.tangent_arc(0, 20)
        self.assertEqual(len(self.sketch.pencil.primitives), 2)
        self.assertIsInstance(self.sketch.pencil.primitives[-1], Arc)
        self.assertAlmostEqual(self.sketch.pencil.points[-1].x.value, 20)
        self.assertAlmostEqual(self.sketch.pencil.points[-1].y.value, 20)
        # TODO check the center
        # center calculation has bugs
        # center = self.sketch.pencil.primitives[-1].get_center()
        # self.assertAlmostEqual(center.x.value, 20)
        # self.assertAlmostEqual(center.y.value, 10)


class TestDrawRoundedCornerThenLineTo(unittest.TestCase):

    def setUp(self):
        self.part = start_component()
        self.sketch = Sketch(self.part.xy())
        self.draw = self.sketch.pencil

    def test_rounded_corner_with_large_radius(self):
        # Drawing a line first
        self.draw.line_to(10, 0)
        with self.assertRaises(ValueError) as context:
            self.draw.rounded_corner_then_line_to(20, 0, 15)
        self.assertEqual(
            str(context.exception),
            "The radius is too large compared to the length of the previous line segment.",
        )

    def test_rounded_corner_with_large_radius_new_line(self):
        # Drawing a line first
        self.draw.line_to(10, 0)
        with self.assertRaises(ValueError) as context:
            self.draw.rounded_corner_then_line_to(11, 0, 5)
        self.assertEqual(
            str(context.exception),
            "The radius is too large compared to the length of the new line segment.",
        )

    def test_rounded_corner_then_line_to_success(self):
        # Drawing a line first
        self.draw.line_to(10, 0)
        self.draw.rounded_corner_then_line_to(20, 10, 2)
        self.assertEqual(len(self.draw.primitives), 3)
        self.assertIsInstance(self.draw.primitives[-2], Arc)
        self.assertIsInstance(self.draw.primitives[-1], Line)
        self.assertAlmostEqual(self.draw.points[-1].x.value, 20)
        self.assertAlmostEqual(self.draw.points[-1].y.value, 10)


if __name__ == "__main__":
    unittest.main()
