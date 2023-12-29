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
        return brick


class LegoRow:
    def __init__(self, n_length=12):
        self.n_length = n_length

    def get_assy(self):
        """A row of bricks"""
        if self.n_length % 4 != 0:
            raise ("needs a length to be divisible by 4")
        self.assy = start_assembly()
        n_4_bricks = int(self.n_length / 4)
        for i in range(n_4_bricks):
            br = LegoBrick(4, 2).get_part()
            br.paint(color_choices[random.randint(0, len(color_choices) - 1)])
            br.translate_x(32 * i)  # length of brick
            self.assy.add_component(br)
        return self.assy


class LegoFort:
    def __init__(self, n_length=8, n_width=8):
        self.n_length = n_length
        self.n_width = n_width
        self.assy = start_assembly()

    def get_layer(self, left=False):
        layer = start_assembly()
        factor = int(left is False)

        # Perimeter of 4 layers
        row1 = LegoRow(self.n_length).get_assy()
        row2 = LegoRow(self.n_width).get_assy()
        row2.rotate(angle=np.pi / 2)
        row2.translate_x(-8 - factor * 2 * 8)
        row2.translate_y(24 - factor * 2 * 8)
        # row2.translate_x(24, rotate=True)
        row3 = LegoRow(self.n_length).get_assy()
        row3.translate_y((self.n_width) * 8)
        row3.translate_x((1 - 2 * factor) * 2 * 8)
        row4 = LegoRow(self.n_width).get_assy()
        row4.rotate(angle=np.pi / 2)
        row4.translate_x(8 * self.n_length - 8 - factor * 2 * 8)
        row4.translate_y(8 + factor * 2 * 8)

        for r in [row1, row2, row3, row4]:
            layer.add_component(r)
        return layer

    def get_assy(self):
        l1 = self.get_layer(left=True)
        self.assy.add_component(l1)
        l2 = self.get_layer()
        l2.translate([16, 0, 10])
        self.assy.add_component(l2)
        return self.assy


show(LegoFort().get_assy())
