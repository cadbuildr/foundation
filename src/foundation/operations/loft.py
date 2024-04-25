from foundation.operations.base import Operation
from foundation.types.node import Node
from foundation.types.node_children import NodeChildren
from foundation.sketch.closed_sketch_shape import ClosedSketchShapeTypes
from foundation.sketch.sketch import Sketch


class LoftChildren(NodeChildren):
    shapes: list[ClosedSketchShapeTypes]  # list of shapes to loft between
    sketchs: list[Sketch]  # list of sketches to loft between


class Loft(Operation, Node):
    children_class = LoftChildren

    def __init__(
        self,
        shapes: list[ClosedSketchShapeTypes],
    ):
        Operation.__init__(self)
        Node.__init__(self, parents=[])
        self.children.set_shapes(shapes)
        self.children.set_sketchs([shape.sketch for shape in shapes])

        self.shapes = self.children.shapes
        self.sketchs = self.children.sketchs

        self.params = {}


LoftChildren.__annotations__["shapes"] = list[ClosedSketchShapeTypes]
LoftChildren.__annotations__["sketchs"] = list[Sketch]
