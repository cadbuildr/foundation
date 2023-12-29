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
                c = Circle(center, SMALL_CIRCLE / 2, 20)
                e = Extrusion(c, CIRCLE_HEIGHT, self.height)
                brick.add_operation(e)

    def get_part(self):
        brick = start_component()
        self.get_outer_extrusion(brick)
        self.get_inner_extrusion(brick)
        self.get_circles(brick)
        self.get_inside_circles(brick)
        return brick


parameters = ParameterUI(
    {
        "n_length": {"values": range(1, 10), "default": 4},
        "n_width": {"values": range(1, 10), "default": 2},
        "short_height": {"values": [True, False], "default": False},
    }
)

show_with_params(LegoBrick, parameters)
