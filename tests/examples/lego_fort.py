# %%
from __future__ import annotations

from cadbuildr.foundation import *
import numpy as np
import random

# random color in red, green, blue, yellow, purple, cyan
color_choices = ["red", "green", "blue", "yellow", "purple", "cyan"]

from cadbuildr.foundation import *
from cadbuildr.foundation.interface.interface import (
    Interface,
    Spec,
    DistanceSpec,
    RectangularPatternSpec,
    FixedTranslationConstraint,
    FixedRotationConstraint,
)


class LegoBrickInterface(Interface):
    SPECS = [
        DistanceSpec("WALL_THICKNESS", 1.2),
        DistanceSpec("HEIGHT", 9.6),
        DistanceSpec("CIRCLE_DIAMETER", 4.8),
        DistanceSpec("CIRCLE_HEIGHT", 1.7),
        DistanceSpec("DIM_FACTOR", 8),
        DistanceSpec("SMALL_CIRCLE", 2.6),
        DistanceSpec("CLEARANCE", 0.2),
    ]

    def clip(
        self,
        brick: Part | Assembly,
        other_brick: Part | Assembly,
        n_x: int = 0,
        n_y: int = 0,
    ):
        """clip a brick on top of another one with an offset"""
        offset_x = n_x * self.DIM_FACTOR.value
        offset_y = n_y * self.DIM_FACTOR.value
        offset_z = self.HEIGHT.value
        self.add_constraint(
            FixedTranslationConstraint(
                brick, other_brick, [offset_x, offset_y, offset_z]
            )
        )

    def stick(
        self,
        brick: LegoBrick,
        other_brick: Part | Assembly,
        position: str = "left",
    ):
        positions = {
            # "left": [-brick.length - (other_brick.length - brick.length) / 2, 0, 0],
            # "right": [brick.length + (other_brick.length - brick.length) / 2, 0, 0],
            # "front": [0, -brick.width - (other_brick.width - brick.width) / 2, 0],
            # "back": [0, brick.width + (other_brick.width - brick.width) / 2, 0],
            "left": [
                -brick.n_length + (brick.brick_length - other_brick.brick_length) / 2,
                (brick.brick_width - other_brick.brick_width) / 2,
                0,
            ],
            "right": [
                brick.n_length - (brick.brick_length - other_brick.brick_length) / 2,
                -(brick.brick_width - other_brick.brick_width) / 2,
                0,
            ],
            "front": [
                -(brick.brick_length - other_brick.brick_length) / 2,
                -brick.n_width - (brick.brick_length - other_brick.brick_length) / 2,
                0,
            ],
            "back": [
                (brick.brick_length - other_brick.brick_length) / 2,
                brick.n_width + (brick.brick_length - other_brick.brick_length) / 2,
                0,
            ],
        }

        print(np.array(positions[position]) * self.DIM_FACTOR)

        self.add_constraint(
            FixedTranslationConstraint(
                brick,
                other_brick,
                list(np.array(positions[position]) * self.DIM_FACTOR),
            )
        )


class LegoBrick(Part):
    def __init__(self, n_length=2, n_width=2, short_height=False):
        super().__init__()
        self.interface = LegoBrickInterface()

        self.n_length = self.brick_length = n_length
        self.n_width = self.brick_width = n_width
        self.circle_pattern = RectangularPatternSpec(
            "circle_pattern",
            x_spacing=self.interface.DIM_FACTOR,
            y_spacing=self.interface.DIM_FACTOR,
            n_x=n_length,
            n_y=n_width,
        )

        self.length = (
            self.n_length * self.interface.DIM_FACTOR - self.interface.CLEARANCE
        )
        self.width = self.n_width * self.interface.DIM_FACTOR - self.interface.CLEARANCE
        if short_height:
            self.height = self.interface.HEIGHT.value / 3
        else:
            self.height = self.interface.HEIGHT.value

        self.get_outer_extrusion()
        self.get_inner_extrusion()
        self.get_circles()
        self.get_inside_circles()

    def get_outer_extrusion(self):
        s = Sketch(self.xy())
        square = Rectangle.from_center_and_sides(s.origin, self.length, self.width)
        e = Extrusion(square, self.height)
        self.add_operation(e)

    def get_inner_extrusion(self):
        s = Sketch(self.xy())
        inner_length = self.length - self.interface.WALL_THICKNESS * 2
        inner_width = self.width - self.interface.WALL_THICKNESS * 2
        square = Rectangle.from_center_and_sides(s.origin, inner_length, inner_width)
        e = Extrusion(
            square,
            self.height - (self.interface.CIRCLE_HEIGHT - self.interface.CLEARANCE),
            cut=True,
        )
        self.add_operation(e)

    def get_circles(self):
        plane = self.xy()
        s = Sketch(plane)
        x_offset = -self.length / 2 + self.interface.DIM_FACTOR / 2
        y_offset = -self.width / 2 + self.interface.DIM_FACTOR / 2
        circles = self.circle_pattern.apply(
            lambda x, y: Circle(
                Point(s, x + x_offset, y + y_offset), self.interface.CIRCLE_DIAMETER / 2
            )
        )
        for c in circles:
            e = Extrusion(c, self.height, self.height + self.interface.CIRCLE_HEIGHT)
            self.add_operation(e)

    def get_inside_circles(self):
        plane = self.xy()
        s = Sketch(plane)
        x_offset = -self.length / 2 + self.interface.DIM_FACTOR / 2
        y_offset = -self.width / 2 + self.interface.DIM_FACTOR / 2

        circles = self.circle_pattern.apply(
            lambda x, y: Circle(
                Point(s, x + x_offset, y + y_offset), self.interface.SMALL_CIRCLE / 2
            )
        )
        for c in circles:
            e = Extrusion(c, self.interface.CIRCLE_HEIGHT.value, self.height)
            self.add_operation(e)

    def clip(self, other_brick: LegoBrick, n_x: int = 0, n_y: int = 0):
        self.interface.clip(self, other_brick, n_x, n_y)

    def stick(self, other_brick: LegoBrick, position: str = "left"):
        self.interface.stick(self, other_brick, position)


# show(LegoBrick(4, 2))


class ClipTest(Assembly):
    def __init__(self):
        super().__init__()
        lego = LegoBrick(4, 2)
        lego2 = LegoBrick(4, 2)
        self.add_component(lego)
        lego.clip(lego2, 2, 0)
        lego.interface.apply_constraints(self)


# show(ClipTest())


class LegoRowOrStack(Assembly):
    def __init__(
        self, brick_dim: str = "4x2", orientation: str = "front", n_bricks: int = 2
    ):
        """
        Initialize a LegoRow with specified brick dimensions and orientation.

        :param brick_dim: Dimensions of the bricks in the format "NxM", e.g., "4x2".
        :param orientation: Direction in which bricks are aligned. Options: "left", "right", "front", "back".
        :param n_length: Number of bricks in the row.
        """
        super().__init__()
        self.brick_length, self.brick_width = map(int, brick_dim.lower().split("x"))
        self.orientation = orientation.lower()
        self.n_bricks = n_bricks

        self.interface = LegoBrickInterface()
        # Validate orientation
        if self.orientation not in ["left", "right", "front", "back", "top", "bottom"]:
            raise ValueError(
                "Orientation must be one of 'left', 'right', 'front', 'back'."
            )

        if self.orientation in ["left", "right"]:
            self.n_length = self.brick_length * self.n_bricks
            self.n_width = self.brick_width
        elif self.orientation in ["front", "back"]:
            self.n_length = self.brick_length
            self.n_width = self.brick_width * self.n_bricks
        elif self.orientation in ["top", "bottom"]:
            self.n_length = self.brick_length
            self.n_width = self.brick_width

        # Create bricks based on dimensions and orientation
        prev_brick = None

        for i in range(n_bricks):
            brick = LegoBrick(n_length=self.brick_length, n_width=self.brick_width)
            brick.paint(random.choice(color_choices))

            if prev_brick:
                # Stick the current brick to the previous brick based on orientation
                if self.orientation == "top":
                    self.interface.clip(prev_brick, brick)
                elif self.orientation == "bottom":
                    self.interface.clip(brick, prev_brick)
                else:
                    self.interface.stick(prev_brick, brick, self.orientation)
            else:
                self.add_component(brick)

            prev_brick = brick

        self.interface.apply_constraints(self)
        print(
            f"LegoRow initialized with {self.n_length} long row and a width { self.n_width} oriented to the {self.orientation}."
        )


class LegoRow(LegoRowOrStack):
    def __init__(
        self, brick_dim: str = "4x2", orientation: str = "front", n_length: int = 12
    ):
        super().__init__(brick_dim, orientation, n_length)


class LegoStack(LegoRowOrStack):
    def __init__(
        self, brick_dim: str = "4x2", orientation: str = "top", n_width: int = 12
    ):
        super().__init__(brick_dim, orientation, n_width)


# show(LegoRow(brick_dim="4x2", orientation="left", n_length=4))


# show(LegoStack(brick_dim="4x2", orientation="top", n_width=4))


class LegoPyramid(Assembly):
    def __init__(self, brick_dim: str = "4x2", n_layers: int = 5):
        super().__init__()
        self.brick_length, self.brick_width = map(int, brick_dim.lower().split("x"))
        self.n_layers = n_layers
        self.interface = LegoBrickInterface()
        self.brick_dim = brick_dim

        # Create and position layers
        n_bricks = self.n_layers
        current_row = LegoRow(self.brick_dim, "right", n_bricks)
        self.add_component(current_row)
        for layer in range(1, n_layers):
            n_bricks -= 1
            print(n_bricks)
            prev_row = current_row
            current_row = LegoRow(self.brick_dim, "right", n_bricks)
            # clip with offset
            self.interface.clip(prev_row, current_row, self.brick_length // 2, 0)

        self.interface.apply_constraints(self)


# show(LegoPyramid("4x2", 4))


class LegoFort(Assembly):
    def __init__(self, n_length=8, n_width=8, n_layers=3):
        super().__init__()
        self.n_length = n_length
        self.n_width = n_width
        self.n_layers = n_layers
        self.interface = LegoBrickInterface()
        self.build_fort()

    def build_fort(self):
        prev_layer = None
        for layer_number in range(self.n_layers):
            # Alternate brick orientation for interlocking
            direction = (
                "clockwise"  # TODO if layer_number % 2 == 0 else "anticlockwise"
            )
            current_layer = self.build_perimeter("4x2", direction)

            if prev_layer:
                # Clip the current layer to the previous layer
                self.interface.clip(prev_layer, current_layer)
            else:
                # Add the first layer to the assembly
                self.add_component(current_layer)

            prev_layer = current_layer

        # Apply interface constraints
        self.interface.apply_constraints(self)

    def build_perimeter(self, brick_dim, direction="clockwise"):
        perimeter = Assembly()

        # Create rows for each side
        front_row = LegoRow(brick_dim, "right", self.n_length // 4)
        right_row = LegoRow(
            "4x2" if brick_dim == "2x4" else "2x4", "back", self.n_width // 4
        )
        back_row = LegoRow(brick_dim, "left", self.n_length // 4)
        left_row = LegoRow(
            "4x2" if brick_dim == "2x4" else "2x4", "front", self.n_width // 4
        )

        # Add rows to perimeter
        perimeter.add_component(front_row)
        # Connect the rows
        if direction == "clockwise":
            print("perimeter interface ")
            self.interface.stick(front_row, right_row, "right")
            self.interface.stick(right_row, back_row, "back")
            self.interface.stick(back_row, left_row, "left")

        return perimeter


show(LegoFort(n_length=4, n_width=4, n_layers=2))
