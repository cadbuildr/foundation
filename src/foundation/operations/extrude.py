from foundation.operations.base import Operation
from foundation.types.node import Node

from foundation.sketch.base import SketchShape
from foundation.sketch.closed_sketch_shape import Circle, ClosedSketchShape
from foundation.geometry.frame import OriginFrame

from foundation.types.parameters import (
    UnCastFloat,
    UnCastInt,
    UnCastBool,
    UnCastString,
    cast_to_float_parameter,
    cast_to_int_parameter,
    cast_to_bool_parameter,
    cast_to_string_parameter,
)


class Extrusion(Operation, Node):
    parent_types = [OriginFrame]

    def __init__(
        self,
        shape: ClosedSketchShape,
        end: UnCastFloat = 1.0,
        start: UnCastFloat = 0.0,
        cut: UnCastBool = False,
    ):
        Operation.__init__(self)
        Node.__init__(self, parents=[])
        self.sketch = shape.sketch
        self.register_child(shape)
        # print("Registered child", shape.sketch, "with id " + str(shape.id))
        self.register_child(shape.sketch)
        self.start = cast_to_float_parameter(start)
        self.end = cast_to_float_parameter(end)
        self.cut = cast_to_bool_parameter(cut)
        self.register_child(self.start)
        self.register_child(self.end)
        self.register_child(self.cut)

        self.params = {
            "n_shape": shape.id,
            "n_start": self.start.id,
            "n_end": self.end.id,
            "n_cut": self.cut.id,
            "n_sketch": shape.sketch.id,
        }

    def get_frame(self):
        # parent 0 is sketchShape
        return self.sketch.frame


# A hole is an extrusion with cut set to True a point ( on a defined plane + sketch), a diameter, and a depth of cut.
# NOTE this is quite restrictive as a definition ( different type of holes for machining will need to be implemented
# including threads, profiles ... )
class Hole(Extrusion):
    def __init__(self, point, radius, depth):
        shape = Circle(point, radius)
        super().__init__(shape, depth, cut=True)
        self.shape = shape
        self.diameter = radius
        self.point = point
