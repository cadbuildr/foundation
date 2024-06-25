import unittest
from foundation import Sketch, Point, Line, start_component
import numpy as np


class TestLine(unittest.TestCase):
    def setUp(self):
        part = start_component()
        self.sketch = Sketch(part.xy())
        self.p1 = Point(self.sketch, 0, 0)
        self.p2 = Point(self.sketch, 3, 3)
        self.line = Line(self.p1, self.p2)

    def test_length(self):
        expected_length = 3 * np.sqrt(2)
        self.assertAlmostEqual(self.line.length(), expected_length)

    def test_translate(self):
        dx, dy = 1, 2
        translated_line = self.line.translate(dx, dy)
        self.assertEqual(translated_line.p1.x.value, 1)
        self.assertEqual(translated_line.p1.y.value, 2)
        self.assertEqual(translated_line.p2.x.value, 4)
        self.assertEqual(translated_line.p2.y.value, 5)

    def test_rotate(self):
        angle = np.pi / 2  # Radians
        center = Point(self.sketch, 0, 0)
        rotated_line = self.line.rotate(angle, center)
        self.assertAlmostEqual(rotated_line.p1.x.value, 0)
        self.assertAlmostEqual(rotated_line.p1.y.value, 0)
        self.assertAlmostEqual(rotated_line.p2.x.value, -3)
        self.assertAlmostEqual(rotated_line.p2.y.value, 3)

    def test_distance_to_point(self):
        p = Point(self.sketch, 0, 0)
        # test for point on the line
        self.assertAlmostEqual(self.line.distance_to_point(p), 0.0)
        p = Point(self.sketch, 0, 1)
        expected = 1.0 / np.sqrt(2)
        self.assertAlmostEqual(self.line.distance_to_point(p), expected)

    def test_closest_point_on_line(self):

        # test with point on the line.
        p0 = Point(self.sketch, 1.0, 1.0)
        expected_closest_point = (1.0, 1.0)
        closest_point = self.line.closest_point_on_line(p0)
        self.assertAlmostEqual(
            closest_point.x.value,
            expected_closest_point[0],
        )
        self.assertAlmostEqual(
            closest_point.y.value,
            expected_closest_point[1],
            # "Closest point y-coordinate is incorrect.",
        )
        # test with other point
        p0 = Point(self.sketch, 0.0, 1.0)
        expected_closest_point = (0.5, 0.5)
        closest_point = self.line.closest_point_on_line(p0)
        self.assertAlmostEqual(
            closest_point.x.value,
            expected_closest_point[0],
        )
        self.assertAlmostEqual(
            closest_point.y.value,
            expected_closest_point[1],
            # "Closest point y-coordinate is incorrect.",
        )

    def test_line_intersection(self):
        p3 = Point(self.sketch, 0, 1)
        p4 = Point(self.sketch, 1, 0)
        line_b = Line(p3, p4)
        intersection_point = Line.intersection(self.line, line_b)
        expected_intersection = (0.5, 0.5)
        self.assertAlmostEqual(intersection_point.x.value, expected_intersection[0])
        self.assertAlmostEqual(intersection_point.y.value, expected_intersection[1])

    def test_tangent(self):
        dx, dy = self.line.tangent()
        self.assertAlmostEqual(dx, 1.0 / np.sqrt(2))
        self.assertAlmostEqual(dy, 1.0 / np.sqrt(2))


if __name__ == "__main__":
    unittest.main()
