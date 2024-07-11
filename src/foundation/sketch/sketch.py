from foundation.types.node import Node
from foundation.sketch.point import Point
from foundation.sketch.draw import Draw
from foundation.geometry.plane import PlaneFromFrame
from foundation.types.node_children import NodeChildren
from typing import List


from foundation.sketch.closed_sketch_shape import (
    ClosedSketchShape,
    CustomClosedShape,
    Polygon,
)
from foundation.sketch.point import Point, PointWithTangent
from foundation.sketch.rectangle import Rectangle
from foundation.sketch.primitives.line import Line

from foundation.sketch.primitives.arc import Arc, EllipseArc


SketchElementTypes = (
    ClosedSketchShape
    | Line
    | Arc
    | EllipseArc
    | Rectangle
    | Polygon
    | CustomClosedShape
    | Point
    | PointWithTangent
)


class SketchChildren(NodeChildren):
    plane: PlaneFromFrame
    origin: Point
    elements = List[SketchElementTypes]


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
        self.children.set_elements([])
        self.children.set_origin(SketchOrigin(self))

        # shortcuts
        self.plane = self.children.plane
        self.origin = self.children.origin
        self.frame = self.plane.frame
        # print("XXXChildren of sketch  are ", self.children)
        self.params = {}
        self.pencil = Draw(self)

    def add_element(self, element: SketchElementTypes):
        self.children._children["elements"].append(element)


class SketchOrigin(Point):
    def __init__(self, sketch: Sketch):
        super().__init__(sketch, 0.0, 0.0)


SketchChildren.__annotations__["plane"] = PlaneFromFrame
SketchChildren.__annotations__["origin"] = Point
SketchChildren.__annotations__["elements"] = List[SketchElementTypes]
