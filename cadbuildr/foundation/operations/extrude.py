from cadbuildr.foundation.operations.base import Operation
from cadbuildr.foundation.types.node import Node

from cadbuildr.foundation.sketch.point import Point
from cadbuildr.foundation.sketch.closed_sketch_shape import Circle, ClosedSketchShape
from cadbuildr.foundation.types.node_children import NodeChildren
from cadbuildr.foundation.sketch.sketch import Sketch
from cadbuildr.foundation.types.parameters import (
    UnCastFloat,
    UnCastBool,
    UnCastString,
    cast_to_float_parameter,
    cast_to_bool_parameter,
    cast_to_string_parameter,
    FloatParameter,
    BoolParameter,
    StringParameter,
)
from typing import Sequence

from cadbuildr.foundation.sketch.closed_sketch_shape import ClosedSketchShapeTypes


class ExtrusionChildren(NodeChildren):
    shape: ClosedSketchShapeTypes | Sequence[ClosedSketchShapeTypes]
    start: FloatParameter | Sequence[FloatParameter]
    end: FloatParameter | Sequence[FloatParameter]
    cut: BoolParameter | Sequence[BoolParameter]
    profile: StringParameter | Sequence[StringParameter]
    end_factor: FloatParameter | Sequence[FloatParameter]
    twist_angle: FloatParameter | Sequence[FloatParameter]
    sketch: Sketch


class Extrusion(Operation, Node):
    children_class = ExtrusionChildren

    def __init__(
        self,
        shape: ClosedSketchShapeTypes | Sequence[ClosedSketchShapeTypes],
        end: UnCastFloat | Sequence[UnCastFloat] = 1.0,
        start: UnCastFloat | Sequence[UnCastFloat] = 0.0,
        cut: UnCastBool | Sequence[UnCastBool] = False,
        profile: UnCastString | Sequence[UnCastString] = "linear",
        end_factor: UnCastFloat | Sequence[UnCastFloat] = 1.0,
        twist_angle: UnCastFloat | Sequence[UnCastFloat] = 0.0,
    ):
        Operation.__init__(self)
        Node.__init__(self, parents=[])
        self.children.set_shape(shape)
        if isinstance(shape, Sequence):
            # assert they all have the same sketch
            for s in shape:
                if s.sketch != shape[0].sketch:
                    raise ValueError("All shapes must have the same sketch")
                # Check that start, end, cut, profile, end_factor and twist_angle are the same length as shape or a single value
                if (
                    (isinstance(start, Sequence) and len(start) != len(shape))
                    or (isinstance(end, Sequence) and len(end) != len(shape))
                    or (isinstance(cut, Sequence) and len(cut) != len(shape))
                    or (isinstance(profile, Sequence) and not isinstance(profile, str) and len(profile) != len(shape))
                    or (isinstance(end_factor, Sequence) and len(end_factor) != len(shape))
                    or (isinstance(twist_angle, Sequence) and len(twist_angle) != len(shape))
                ):
                    raise ValueError(
                        "start, end, cut, profile, end_factor and twist_angle must be the same length as shape or a single value"
                    )
            sketch = shape[0].sketch
        else:
            sketch = shape.sketch
        self.children.set_sketch(sketch)
        if isinstance(start, Sequence):
            start_list = [cast_to_float_parameter(s) for s in start]
            self.children.set_start(start_list)
        else:
            self.children.set_start(cast_to_float_parameter(start))
        if isinstance(end, Sequence):
            end_list = [cast_to_float_parameter(e) for e in end]
            self.children.set_end(end_list)
        else:
            self.children.set_end(cast_to_float_parameter(end))
        if isinstance(cut, Sequence):
            cut_list = [cast_to_bool_parameter(c) for c in cut]
            self.children.set_cut(cut_list)
        else:
            self.children.set_cut(cast_to_bool_parameter(cut))
        if isinstance(profile, Sequence) and not isinstance(profile, str):
            profile_list = [cast_to_string_parameter(p) for p in profile]
            self.children.set_profile(profile_list)
        else:
            self.children.set_profile(cast_to_string_parameter(profile))
        if isinstance(end_factor, Sequence):
            end_factor_list = [cast_to_float_parameter(ef) for ef in end_factor]
            self.children.set_end_factor(end_factor_list)
        else:
            self.children.set_end_factor(cast_to_float_parameter(end_factor))
        if isinstance(twist_angle, Sequence):
            twist_angle_list = [cast_to_float_parameter(ta) for ta in twist_angle]
            self.children.set_twist_angle(twist_angle_list)
        else:
            self.children.set_twist_angle(cast_to_float_parameter(twist_angle))

        # shortcuts
        self.shape = self.children.shape
        self.sketch = self.children.sketch
        self.start = self.children.start
        self.end = self.children.end
        self.cut = self.children.cut
        self.profile = self.children.profile
        self.end_factor = self.children.end_factor
        self.twist_angle = self.children.twist_angle

        self.params = {}

    def get_frame(self):
        # parent 0 is SketchElement
        return self.sketch.frame


ExtrusionChildren.__annotations__["shape"] = (
    ClosedSketchShapeTypes | list[ClosedSketchShapeTypes]
)
ExtrusionChildren.__annotations__["start"] = FloatParameter | Sequence[FloatParameter]
ExtrusionChildren.__annotations__["end"] = FloatParameter | Sequence[FloatParameter]
ExtrusionChildren.__annotations__["cut"] = BoolParameter | Sequence[BoolParameter]
ExtrusionChildren.__annotations__["profile"] = StringParameter | Sequence[StringParameter]
ExtrusionChildren.__annotations__["end_factor"] = FloatParameter | Sequence[FloatParameter]
ExtrusionChildren.__annotations__["twist_angle"] = FloatParameter | Sequence[FloatParameter]
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
