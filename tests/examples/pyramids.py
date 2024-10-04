from foundation import *
import random


class Cube:
    def __init__(self, size=20):
        self.size = size

    def get_part(self):
        cube = Part()
        # Create a Sketch from XY Plane
        s = Sketch(cube.xy())
        square = Square.from_center_and_side(s.origin, self.size)
        e = Extrusion(square, self.size)
        cube.add_operation(e)

        # random color in red, green, blue, yellow, purple, cyan
        color_choices = ["red", "green", "blue", "yellow", "purple", "cyan"]
        cube.paint(color_choices[random.randint(0, len(color_choices) - 1)])

        return cube


class Pyramid:
    def __init__(self, depth=2, cube_size=20):
        self.depth = depth
        self.cube_size = cube_size
        self.assy = Assembly()

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


# leave this line it's used for loading locally examples
# show(Cube().get_part())
# show(Pyramid(depth=5).get_assy())
