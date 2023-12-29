from foundation.operations.base import Operation
from foundation.types.node import Node
from foundation.sketch.base import SketchShape
from foundation.sketch.axis import Axis
from foundation.types.types import (
    UnCastBool,
    cast_to_bool_parameter,
)


class Lathe(Operation, Node):
    """A Lathe operation is a closed shape,
    that is revolved around an axis, to make as solid"""

    def __init__(self, shape: SketchShape, axis: Axis, cut: UnCastBool = False):
        Operation.__init__(self)
        Node.__init__(self, parents=[])
        self.axis = axis
        self.shape = shape
        self.cut = cast_to_bool_parameter(cut)
        self.register_child(self.axis)
        self.register_child(self.cut)
        self.register_child(shape)
        self.register_child(shape.sketch)
        self.params = {
            "n_shape": shape.id,
            "n_axis": axis.id,
            "n_cut": self.cut.id,
            "n_sketch": shape.sketch.id,
        }

    def get_frame(self):
        # parent 0 is sketchShape
        return self.shape.get_frame()
