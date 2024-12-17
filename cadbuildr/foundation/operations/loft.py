from cadbuildr.foundation.operations.base import Operation
from cadbuildr.foundation.types.node import Node
from cadbuildr.foundation.types.node_children import NodeChildren
from cadbuildr.foundation.sketch.closed_sketch_shape import ClosedSketchShapeTypes
from cadbuildr.foundation.sketch.sketch import Sketch

from typing import Sequence, List


class LoftChildren(NodeChildren):
    shapes: List[ClosedSketchShapeTypes]  # list of shapes to loft between
    sketchs: List[Sketch]  # list of sketches to loft between


class Loft(Operation, Node):
    children_class = LoftChildren

    def __init__(
        self,
        shapes: Sequence[ClosedSketchShapeTypes],
    ):
        Operation.__init__(self)
        Node.__init__(self, parents=[])
        self.children.set_shapes(shapes)
        self.children.set_sketchs([shape.sketch for shape in shapes])

        self.shapes = self.children.shapes
        self.sketchs = self.children.sketchs

        self.params = {}


LoftChildren.__annotations__["shapes"] = List[ClosedSketchShapeTypes]
LoftChildren.__annotations__["sketchs"] = List[Sketch]
