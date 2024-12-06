from cadbuildr.foundation.types.node_interface import NodeInterface
from cadbuildr.foundation.types.node_children import NodeChildren
from cadbuildr.foundation.types.types_3d.point_3d import Point3D
from cadbuildr.foundation.types.node import Node
from cadbuildr.foundation.types.parameters import (
    FloatParameter,
    BoolParameter,
    UnCastFloat,
    UnCastBool,
    cast_to_float_parameter,
    cast_to_bool_parameter,
)


class Curve3D(NodeInterface):
    """Base class for 3D curves."""

    def __init__(self):
        super().__init__()


class Line3DChildren(NodeChildren):
    start: Point3D
    end: Point3D


class Line3D(Curve3D, Node):
    pass
    # TODO: Implement the following classes


# 3 points define a unique arc (note : they need to be on the same plane)
class Arc3DChildren(NodeChildren):
    p1: Point3D
    p2: Point3D
    p3: Point3D


class Arc3D(Curve3D, Node):
    # TODO
    pass


class HelixChildren(NodeChildren):
    pitch: UnCastFloat
    height: UnCastFloat
    radius: UnCastFloat
    center: Point3D
    dir: Point3D
    lefthand: UnCastBool


class Helix3D(Curve3D, Node):
    """A Helix curve,
    starting at (center.x + radius.x, center.y, center.z)"""

    children_class = HelixChildren

    def __init__(
        self,
        pitch: float,
        height: float,
        radius: float,
        center: Point3D = Point3D(0, 0, 0),
        dir: Point3D = Point3D(0, 0, 1),
        lefthand: bool = False,
    ):
        Node.__init__(self)
        Curve3D.__init__(self)

        self.children.set_pitch(cast_to_float_parameter(pitch))
        self.children.set_height(cast_to_float_parameter(height))
        self.children.set_radius(cast_to_float_parameter(radius))
        self.children.set_center(center)
        self.children.set_dir(dir)
        self.children.set_lefthand(cast_to_bool_parameter(lefthand))
        self.params = {}


class Ellipse3DChildren(NodeChildren):
    # TODO
    pass


class Ellipse3D(Curve3D, Node):
    # TODO
    pass


class Spline3DChildren(NodeChildren):
    points: list[Point3D]


class Spline3D(Curve3D, Node):
    # TODO
    pass


Curve3DTypes = Helix3D  # U

HelixChildren.__annotations__["pitch"] = FloatParameter
HelixChildren.__annotations__["height"] = FloatParameter
HelixChildren.__annotations__["radius"] = FloatParameter
HelixChildren.__annotations__["center"] = Point3D
HelixChildren.__annotations__["dir"] = Point3D
HelixChildren.__annotations__["lefthand"] = BoolParameter
