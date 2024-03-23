# %%
from foundation import *


class Cube:
    def __init__(self, size=30):
        self.size = size

    def get_part(self):
        cube = start_component()
        # Create a Sketch from XY Plane
        s = Sketch(cube.xy())
        square = Square.from_center_and_side(s.origin, self.size)
        e = Extrusion(square, self.size)
        cube.add_operation(e)
        cube.paint("blue")
        return cube


class MonoCubeAssy:
    def __init__(self):
        self.assy = start_assembly()
        self.cube_size = 10

    def get_assy(self):
        cube = Cube(self.cube_size).get_part()
        cube.translate([self.cube_size, 0, 0])
        self.assy.add_component(cube)

        return self.assy


# This code will load the cube and display it
showExt(MonoCubeAssy().get_assy())


# %%


class Pyramid:
    def __init__(self, depth=2, cube_size=20):
        self.depth = depth
        self.cube_size = cube_size
        self.assy = start_assembly()

    def get_assy(self, total_depth=None):
        """Recursive function"""
        if total_depth is None:
            total_depth = self.depth

        top_cube = Cube(self.cube_size).get_part()
        if self.depth > 1:
            p_left = Pyramid(self.depth - 1).get_assy(total_depth)
            p_right = Pyramid(self.depth - 1).get_assy(total_depth)

            # move the pyramides by cube_size * 0.6 * (self.depth - 1) sideways and cube_size down
            p_left.translate(
                [self.cube_size * 0.6 * (self.depth - 1), 0, -self.cube_size]
            )

            p_right.translate(
                [-self.cube_size * 0.6 * (self.depth - 1), 0, -self.cube_size]
            )

            self.assy.add_component(top_cube)
            self.assy.add_component(p_left)
            self.assy.add_component(p_right)
            return self.assy
        else:
            self.assy.add_component(top_cube)
            return self.assy


showExt(Pyramid(depth=2).get_assy())

# %%
from foundation import *
import numpy as np
import random

# random color in red, green, blue, yellow, purple, cyan
color_choices = ["red", "green", "blue", "yellow", "purple", "cyan"]

from foundation import *

CLEARANCE = 0.2
WALL_THICKNESS = 1.2
HEIGHT = 9.6
CIRCLE_DIAMETER = 4.8
CIRCLE_DIAMETER_LARGE = 6.5
CIRCLE_HEIGHT = 1.7
DIM_FACTOR = 8
SMALL_CIRCLE = 2.6


class LegoBrick:
    def __init__(self, n_length=2, n_width=2, short_height=False):
        self.n_length = n_length
        self.n_width = n_width

        self.lenght = self.n_length * DIM_FACTOR - CLEARANCE
        self.width = self.n_width * DIM_FACTOR - CLEARANCE
        if short_height:
            self.height = HEIGHT / 3
        else:
            self.height = HEIGHT

    def get_outer_extrusion(self, brick):
        s = Sketch(brick.xy())
        square = Rectangle.from_center_and_sides(s.origin, self.lenght, self.width)
        e = Extrusion(square, self.height)
        brick.add_operation(e)

    def get_inner_extrusion(self, brick):
        s = Sketch(brick.xy())
        inner_length = self.lenght - WALL_THICKNESS * 2
        inner_width = self.width - WALL_THICKNESS * 2
        square = Rectangle.from_center_and_sides(s.origin, inner_length, inner_width)
        e = Extrusion(square, self.height - (CIRCLE_HEIGHT - CLEARANCE), cut=True)
        brick.add_operation(e)

    def get_circles(self, brick):
        plane = brick.xy()
        s = Sketch(plane)

        for i in range(self.n_length):
            for j in range(self.n_width):
                center = Point(
                    s,
                    (i * DIM_FACTOR - self.lenght / 2) + DIM_FACTOR / 2,
                    (j * DIM_FACTOR - self.width / 2) + DIM_FACTOR / 2,
                )
                c = Circle(center, CIRCLE_DIAMETER / 2)
                e = Extrusion(c, self.height, self.height + CIRCLE_HEIGHT)
                brick.add_operation(e)

    def get_inside_circles(self, brick):
        plane = brick.xy()
        s = Sketch(plane)

        for i in range(self.n_length):
            for j in range(self.n_width):
                center = Point(
                    s,
                    (i * DIM_FACTOR - self.lenght / 2) + DIM_FACTOR / 2,
                    (j * DIM_FACTOR - self.width / 2) + DIM_FACTOR / 2,
                )
                c = Circle(center, SMALL_CIRCLE / 2)
                e = Extrusion(c, CIRCLE_HEIGHT, self.height)
                brick.add_operation(e)

    def get_part(self):
        brick = start_component()
        self.get_outer_extrusion(brick)
        self.get_inner_extrusion(brick)
        self.get_circles(brick)
        self.get_inside_circles(brick)
        brick.paint(random.choice(color_choices))
        return brick


if __name__ == "__main__":
    showExt(LegoBrick().get_part())

# %%
