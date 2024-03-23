from foundation.types.node import Node
from foundation.sketch.point import Point
from foundation.sketch.draw import Draw
from foundation.geometry.plane import PlaneFromFrame
from foundation.types.node_children import NodeChildren


class SketchChildren(NodeChildren):
    plane: PlaneFromFrame
    origin: Point


class Sketch(Node):
    """
    Sketch Node to draw points, lines, shapes ...

    Every sketch has :
    - a plane as a parent
    - a sketch origin(Point, with 0,0 coordinates) as a child
    """

    children_class = SketchChildren

    # TODO check if plane is a PlaneFromFrame
    def __init__(self, plane: PlaneFromFrame):
        super().__init__()

        self.children.set_plane(plane)
        self.children.set_origin(SketchOrigin(self))

        # shortcuts
        self.plane = self.children.plane
        self.origin = self.children.origin
        self.frame = self.plane.frame
        # print("XXXChildren of sketch  are ", self.children)
        self.params = {}
        self.pencil = Draw(self)


class SketchOrigin(Point):
    def __init__(self, sketch: Sketch):
        super().__init__(sketch, 0.0, 0.0)


SketchChildren.__annotations__["plane"] = PlaneFromFrame
SketchChildren.__annotations__["origin"] = Point
