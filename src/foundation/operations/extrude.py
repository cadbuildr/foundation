from foundation.operations.base import Operation
from foundation.types.node import Node

from foundation.sketch.base import SketchElement
from foundation.sketch.closed_sketch_shape import Circle, ClosedSketchShape
from foundation.types.node_children import NodeChildren
from foundation.sketch.sketch import Sketch

from foundation.types.parameters import (
    UnCastFloat,
    UnCastBool,
    cast_to_float_parameter,
    cast_to_bool_parameter,
    FloatParameter,
    BoolParameter,
)

from foundation.sketch.closed_sketch_shape import ClosedSketchShapeTypes


class ExtrusionChildren(NodeChildren):
    shape: ClosedSketchShapeTypes
    start: FloatParameter
    end: FloatParameter
    cut: BoolParameter
    sketch: "Sketch"


class Extrusion(Operation, Node):
    children_class = ExtrusionChildren

    def __init__(
        self,
        shape: ClosedSketchShapeTypes,
        end: UnCastFloat = 1.0,
        start: UnCastFloat = 0.0,
        cut: UnCastBool = False,
    ):
        Operation.__init__(self)
        Node.__init__(self, parents=[])
        self.children.set_shape(shape)
        self.children.set_sketch(shape.sketch)
        self.children.set_start(cast_to_float_parameter(start))
        self.children.set_end(cast_to_float_parameter(end))
        self.children.set_cut(cast_to_bool_parameter(cut))

        # shortcuts
        self.shape = self.children.shape
        self.sketch = self.children.sketch
        self.start = self.children.start
        self.end = self.children.end
        self.cut = self.children.cut

        self.params = {
            # "n_shape": shape.id,
            # "n_start": self.start.id,
            # "n_end": self.end.id,
            # "n_cut": self.cut.id,
            # "n_sketch": shape.sketch.id,
        }

    def get_frame(self):
        # parent 0 is SketchElement
        return self.sketch.frame


ExtrusionChildren.__annotations__["shape"] = ClosedSketchShapeTypes
ExtrusionChildren.__annotations__["start"] = FloatParameter
ExtrusionChildren.__annotations__["end"] = FloatParameter
ExtrusionChildren.__annotations__["cut"] = BoolParameter
ExtrusionChildren.__annotations__["sketch"] = Sketch


# A hole is an extrusion with cut set to True a point ( on a defined plane + sketch), a diameter, and a depth of cut.
# NOTE this is quite restrictive as a definition ( different type of holes for machining will need to be implemented
# including threads, profiles ... )
class Hole(Extrusion):
    def __init__(self, point, radius, depth):
        shape = Circle(point, radius)
        super().__init__(shape=shape, end=depth, cut=True)
        self.diameter = radius
        self.point = point
