# %%
from cadbuildr.foundation import *
import random


class Cube(Part):
    def __init__(self, size=20):
        self.size = size
        # Create a Sketch from XY Plane
        s = Sketch(self.xy())
        square = Square.from_center_and_side(s.origin, self.size)
        e = Extrusion(square, self.size)
        self.add_operation(e)

        # random color in red, green, blue, yellow, purple, cyan
        color_choices = ["red", "green", "blue", "yellow", "purple", "cyan"]
        self.paint(color_choices[random.randint(0, len(color_choices) - 1)])


class Pyramid(Assembly):
    """Recursive Assembly"""

    def __init__(self, depth=2, cube_size=20, total_depth=None):
        self.depth = depth
        self.cube_size = cube_size
        if total_depth is None:
            total_depth = self.depth

        top_cube = Cube(self.cube_size)
        if self.depth > 1:
            p_left = Pyramid(self.depth - 1, cube_size, total_depth)
            p_right = Pyramid(self.depth - 1, cube_size, total_depth)

            # move the pyramides by cube_size * 0.6 * (self.depth - 1) sideways and cube_size down
            p_left.translate(
                [self.cube_size * 0.6 * (self.depth - 1), 0, -self.cube_size]
            )

            p_right.translate(
                [-self.cube_size * 0.6 * (self.depth - 1), 0, -self.cube_size]
            )

            self.add_component(top_cube)
            self.add_component(p_left)
            self.add_component(p_right)
        else:
            self.add_component(top_cube)


# leave this line it's used for loading locally examples
# show(Cube())
show(Pyramid(depth=5))
