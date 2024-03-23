from foundation.operations.base import Operation
from foundation.types.node import Node
from foundation.sketch.base import SketchShape
from foundation.sketch.axis import Axis
from foundation.geometry.frame import Frame
from foundation.types.parameters import (
    UnCastBool,
    cast_to_bool_parameter,
)
from foundation.types.node_children import NodeChildren
from foundation.sketch.closed_sketch_shape import ClosedSketchShapeTypes
from foundation.sketch.sketch import Sketch


class LatheChildren(NodeChildren):
    shape: ClosedSketchShapeTypes
    axis: "Axis"
    cut: UnCastBool
    sketch: "Sketch"


class Lathe(Operation, Node):
    """A Lathe operation is a closed shape,
    that is revolved around an axis, to make as solid"""

    children_class = LatheChildren

    def __init__(
        self, shape: ClosedSketchShapeTypes, axis: Axis, cut: UnCastBool = False
    ):
        Operation.__init__(self)
        Node.__init__(self, parents=[])

        self.children.set_cut(cast_to_bool_parameter(cut))
        self.children.set_shape(shape)
        self.children.set_axis(axis)
        self.children.set_sketch(shape.sketch)

        # shortcuts
        self.axis = self.children.axis
        self.shape = self.children.shape
        self.cut = self.children.cut

        self.params = {}

    def get_frame(self) -> Frame:
        # parent 0 is sketchShape
        return self.shape.get_frame()


LatheChildren.__annotations__["shape"] = ClosedSketchShapeTypes
LatheChildren.__annotations__["axis"] = Axis
LatheChildren.__annotations__["cut"] = UnCastBool
LatheChildren.__annotations__["sketch"] = Sketch
