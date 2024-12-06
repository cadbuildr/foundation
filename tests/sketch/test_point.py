import unittest
from math import sqrt, isclose
from cadbuildr.foundation import Sketch, Part, Point, Arc


class TestArc(unittest.TestCase):
    def setUp(self):
        comp = Part()
        # Operation 1
        self.sketch = Sketch(comp.xy())

    def test_midpoint(self):
        p1 = Point(self.sketch, -1, 0)
        p2 = Point(self.sketch, 1, 0)
        p3 = Point.midpoint(p1, p2)
        self.assertTrue(isclose(p3.x.value, 0))
        self.assertTrue(isclose(p3.y.value, 0))

    def test_distance_between_points(self):
        p1 = Point(self.sketch, -1, 0)
        p2 = Point(self.sketch, 1, 0)
        distance = Point.distance_between_points(p1, p2)
        self.assertTrue(isclose(distance, 2))

    def test_eq(self):
        p1 = Point(self.sketch, -1, 0)
        p2 = Point(self.sketch, -1, 0)
        self.assertEqual(p1, p2)
