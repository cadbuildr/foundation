from foundation.types.node import Node
from foundation.sketch.point import Point
from foundation.sketch.draw import Draw
from foundation.geometry.plane import PlaneFromFrame


class Sketch(Node):
    """
    Sketch Node to draw points, lines, shapes ...

    Every sketch has :
    - a plane as a parent
    - a sketch origin(Point, with 0,0 coordinates) as a child
    """

    # TODO check if plane is a PlaneFromFrame
    def __init__(self, plane: PlaneFromFrame):
        super().__init__()
        self.register_child(plane)
        self.plane = plane
        self.frame = self.plane.frame
        # create sketch origin and adds it as a child
        sketch_origin = SketchOrigin(self)
        self.origin = sketch_origin
        # print("XXXChildren of sketch  are ", self.children)
        self.params = {
            "n_plane": self.plane.id,
            "n_origin": self.origin.id,
        }
        self.pencil = Draw(self)


class SketchOrigin(Point):
    def __init__(self, sketch: Sketch):
        super().__init__(sketch, 0.0, 0.0)
