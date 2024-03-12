# %%
from foundation import *


class Cube:
    def __init__(self, size=20):
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


cube = Cube().get_part()

showExt(cube)
