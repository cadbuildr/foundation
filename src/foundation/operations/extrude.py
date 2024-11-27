from foundation.operations.base import Operation
from foundation.types.node import Node

from foundation.sketch.point import Point
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
    shape: ClosedSketchShapeTypes | list[ClosedSketchShapeTypes]
    start: FloatParameter | list[FloatParameter]
    end: FloatParameter | list[FloatParameter]
    cut: BoolParameter | list[BoolParameter]
    sketch: Sketch


class Extrusion(Operation, Node):
    children_class = ExtrusionChildren

    def __init__(
        self,
        shape: ClosedSketchShapeTypes | list[ClosedSketchShapeTypes],
        end: UnCastFloat | list[UnCastFloat] = 1.0,
        start: UnCastFloat | list[UnCastFloat] = 0.0,
        cut: UnCastBool | list[UnCastBool] = False,
    ):
        Operation.__init__(self)
        Node.__init__(self, parents=[])
        self.children.set_shape(shape)
        if isinstance(shape, list):
            # assert they all have the same sketch
            for s in shape:
                if s.sketch != shape[0].sketch:
                    raise ValueError("All shapes must have the same sketch")
                # Check that start , end and cut are the same length as shape or a single value
                if (
                    (isinstance(start, list) and len(start) != len(shape))
                    or (isinstance(end, list) and len(end) != len(shape))
                    or (isinstance(cut, list) and len(cut) != len(shape))
                ):
                    raise ValueError(
                        "start, end and cut must be the same length as shape or a single value"
                    )
            sketch = shape[0].sketch
        else:
            sketch = shape.sketch
        self.children.set_sketch(sketch)
        if isinstance(start, list):
            start_list = [cast_to_float_parameter(s) for s in start]
            self.children.set_start(start_list)
        else:
            self.children.set_start(cast_to_float_parameter(start))
        if isinstance(end, list):
            end_list = [cast_to_float_parameter(e) for e in end]
            self.children.set_end(end_list)
        else:
            self.children.set_end(cast_to_float_parameter(end))
        if isinstance(cut, list):
            cut_list = [cast_to_bool_parameter(c) for c in cut]
            self.children.set_cut(cut_list)
        else:
            self.children.set_cut(cast_to_bool_parameter(cut))

        # shortcuts
        self.shape = self.children.shape
        self.sketch = self.children.sketch
        self.start = self.children.start
        self.end = self.children.end
        self.cut = self.children.cut

        self.params = {}

    def get_frame(self):
        # parent 0 is SketchElement
        return self.sketch.frame


ExtrusionChildren.__annotations__["shape"] = (
    ClosedSketchShapeTypes | list[ClosedSketchShapeTypes]
)
ExtrusionChildren.__annotations__["start"] = FloatParameter | list[FloatParameter]
ExtrusionChildren.__annotations__["end"] = FloatParameter | list[FloatParameter]
ExtrusionChildren.__annotations__["cut"] = BoolParameter | list[BoolParameter]
ExtrusionChildren.__annotations__["sketch"] = Sketch


# A hole is an extrusion with cut set to True a point ( on a defined plane + sketch), a diameter, and a depth of cut.
# NOTE this is quite restrictive as a definition ( different type of holes for machining will need to be implemented
# including threads, profiles ... )
class Hole(Extrusion):
    def __init__(
        self,
        point: Point,
        radius: UnCastFloat,
        depth: UnCastFloat,
        other_depth: UnCastFloat = 0.0,
    ):
        shape = Circle(point, radius)
        super().__init__(shape=shape, end=depth, start=other_depth, cut=True)
        self.diameter = cast_to_float_parameter(radius)
        self.point = point
