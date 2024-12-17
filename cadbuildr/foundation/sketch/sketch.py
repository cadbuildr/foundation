from __future__ import annotations

from cadbuildr.foundation.types.node import Node
from cadbuildr.foundation.sketch.point import Point
from cadbuildr.foundation.sketch.draw import Draw
from cadbuildr.foundation.geometry.plane import Plane
from cadbuildr.foundation.types.node_children import NodeChildren
from typing import List


from cadbuildr.foundation.sketch.closed_sketch_shape import (
    ClosedSketchShape,
    CustomClosedShape,
    Polygon,
    ClosedSketchShapeTypes,
)
from cadbuildr.foundation.sketch.point import Point, PointWithTangent
from cadbuildr.foundation.sketch.rectangle import Rectangle
from cadbuildr.foundation.sketch.primitives.line import Line

from cadbuildr.foundation.sketch.primitives.arc import Arc, EllipseArc


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
    plane: Plane
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

    # TODO check if plane is a Plane
    def __init__(self, plane: Plane):
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

    def get_shapes(self):
        """elements of type ClosedSketchShapeTypes"""
        return [
            e for e in self.children.elements if isinstance(e, ClosedSketchShapeTypes)
        ]


class SketchOrigin(Point):
    def __init__(self, sketch: Sketch):
        super().__init__(sketch, 0.0, 0.0)


SketchChildren.__annotations__["plane"] = Plane
SketchChildren.__annotations__["origin"] = Point
SketchChildren.__annotations__["elements"] = List[SketchElementTypes]
