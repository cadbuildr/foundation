from foundation.types.node import Node
from foundation.geometry.plane import PlaneBase
from foundation.gcs.constraints.constraints2d_factory import ConstraintsFactory
from foundation.sketch.point import Point
from foundation.sketch.draw import Draw


class SketchOrigin(Point):
    def __init__(self, sketch):
        super().__init__(sketch, 0.0, 0.0)


class Sketch(Node):
    """
    Sketch Node to draw points, lines, shapes ...

    Every sketch has :
    - a plane as a parent
    - a sketch origin(Point, with 0,0 coordinates) as a child
    """

    def __init__(self, plane):
        super().__init__()
        self.register_child(plane)
        self.cf = ConstraintsFactory(self)  # sektch helper for constraints
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

    def add_constraint(self, constraint):
        # TODO add a constraint to the nodes
        pass
