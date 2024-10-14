import unittest
from math import sqrt, isclose
from foundation import Sketch, Part, Point, Arc


class TestArc(unittest.TestCase):
    def setUp(self):
        comp = Part()
        # Operation 1
        self.sketch = Sketch(comp.xy())

    def test_from_two_points_and_radius_valid_example(self):
        # Points (-1,0) and (1,0) with radius 1
        p1 = Point(self.sketch, -1, 0)
        p2 = Point(self.sketch, 1, 0)
        radius = 1
        arc = Arc.from_two_points_and_radius(p1, p2, radius)

        # Calculate the expected p3 coordinates
        expected_p2_x = 0
        expected_p2_y = 1

        # Assert the points are correctly set
        self.assertEqual(arc.p1, p1)
        # third point of arc is the second point
        self.assertEqual(arc.p3, p2)
        self.assertTrue(isclose(arc.p2.x.value, expected_p2_x))
        print(arc.p2)
        print("hello")
        self.assertTrue(isclose(arc.p2.y.value, expected_p2_y))

        # Assert the sketch is correctly associated
        self.assertEqual(arc.sketch, self.sketch)

    def test_from_two_points_and_radius_valid_example_reversed(self):
        # Points (1,0) and (-1,0) with radius 1 (reversed order)
        p1 = Point(self.sketch, 1, 0)
        p2 = Point(self.sketch, -1, 0)
        radius = 1
        arc = Arc.from_two_points_and_radius(p1, p2, radius)

        # Calculate the expected p3 coordinates
        expected_p2_x = 0
        expected_p2_y = -1

        # Assert the points are correctly set
        self.assertEqual(arc.p1, p1)

        self.assertEqual(arc.p3, p2)
        self.assertTrue(isclose(arc.p2.x.value, expected_p2_x))
        self.assertTrue(isclose(arc.p2.y.value, expected_p2_y))

        # Assert the sketch is correctly associated
        self.assertEqual(arc.sketch, self.sketch)

    def test_two_points_with_negative_radius(self):
        # Points (-1,0) and (1,0) with radius -1
        p1 = Point(self.sketch, -1, 0)
        p2 = Point(self.sketch, 1, 0)
        radius = -1
        arc = Arc.from_two_points_and_radius(p1, p2, radius)

        # Calculate the expected p3 coordinates
        expected_p2_x = 0
        expected_p2_y = -1

        # Assert the points are correctly set
        self.assertEqual(arc.p1, p1)
        self.assertEqual(arc.p3, p2)
        self.assertTrue(isclose(arc.p2.x.value, expected_p2_x))
        self.assertTrue(isclose(arc.p2.y.value, expected_p2_y))

        # Assert the sketch is correctly associated
        self.assertEqual(arc.sketch, self.sketch)

    def test_from_two_points_and_radius_invalid(self):
        # Test with points where distance is greater than diameter
        p1 = Point(self.sketch, 0, 0)
        p2 = Point(self.sketch, 4, 0)
        radius = 1
        with self.assertRaises(ValueError):
            Arc.from_two_points_and_radius(p1, p2, radius)
