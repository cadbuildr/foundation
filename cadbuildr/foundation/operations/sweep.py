# TODO
from cadbuildr.foundation.operations.base import Operation
from cadbuildr.foundation.types.node import Node

from cadbuildr.foundation.sketch.base import SketchElement
from cadbuildr.foundation.sketch.closed_sketch_shape import Circle, ClosedSketchShape
from cadbuildr.foundation.types.node_children import NodeChildren
from cadbuildr.foundation.sketch.sketch import Sketch

from cadbuildr.foundation.types.parameters import (
    UnCastFloat,
    UnCastBool,
    cast_to_float_parameter,
    cast_to_bool_parameter,
    FloatParameter,
    BoolParameter,
)
from cadbuildr.foundation.types.types_3d.curve import Curve3DTypes


class SweepChildren(NodeChildren):
    profile: ClosedSketchShape
    path: Curve3DTypes
    sketch: Sketch

    # TODO could add more optional parameters here (frenet, ...)


class Sweep(Operation, Node):
    children_class = SweepChildren

    def __init__(
        self,
        profile: ClosedSketchShape,
        path: Curve3DTypes,
    ):

        Operation.__init__(self)
        Node.__init__(self, parents=[])
        self.children.set_profile(profile)
        self.children.set_path(path)
        self.children.set_sketch(profile.sketch)

        # shortcuts
        self.profile = self.children.profile
        self.path = self.children.path

        self.params = {}


SweepChildren.__annotations__["profile"] = ClosedSketchShape
SweepChildren.__annotations__["path"] = Curve3DTypes
SweepChildren.__annotations__["sketch"] = Sketch
