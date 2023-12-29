from foundation.gcs.constraints.base import FoundationJoints
from foundation.types.point_3d import Point3DWithOrientation
from foundation.types.node import Node
from foundation.types.component import Component
from foundation.geometry.plane import PlaneFromFrame


class AnchorPWO(FoundationJoints, Node):
    parent_types = [Point3DWithOrientation]

    def __init__(self, pwo: Point3DWithOrientation):
        Node.__init__(self, parents=[pwo])
        FoundationJoints.__init__(self)
        self._pwo = pwo


class AnchorComponent(AnchorPWO):
    parent_types = [Component]

    def __init__(self, component: Component):
        AnchorPWO.__init__(self, component.get_origin_frame().point_with_orientation)


class PlaneToPlaneCoincid(FoundationJoints, Node):
    def __init__(self, plane1: PlaneFromFrame, plane2: PlaneFromFrame, opposite=False):
        Node.__init__(self, parents=[plane1, plane2])
        FoundationJoints.__init__(self)


class PointWithOrientationCoincidence(FoundationJoints, Node):
    def __init__(self, point1, point2):
        Node.__init__(self, parents=[point1, point2])
        FoundationJoints.__init__(self)


class SameX3D(FoundationJoints, Node):
    def __init__(self, pwo1, pwo2):
        Node.__init__(self, parents=[pwo1, pwo2])
        FoundationJoints.__init__(self)


class SameY3D(FoundationJoints, Node):
    def __init__(self, pwo1, pwo2):
        Node.__init__(self, parents=[pwo1, pwo2])
        FoundationJoints.__init__(self)


class SameZ3D(FoundationJoints, Node):
    def __init__(self, pwo1, pwo2):
        Node.__init__(self, parents=[pwo1, pwo2])
        FoundationJoints.__init__(self)


class SamePitch3D(FoundationJoints, Node):
    def __init__(self, pwo1, pwo2):
        Node.__init__(self, parents=[pwo1, pwo2])
        FoundationJoints.__init__(self)


class SameRoll3D(FoundationJoints, Node):
    def __init__(self, pwo1, pwo2):
        Node.__init__(self, parents=[pwo1, pwo2])
        FoundationJoints.__init__(self)


class SameYaw3D(FoundationJoints, Node):
    def __init__(self, pwo1, pwo2):
        Node.__init__(self, parents=[pwo1, pwo2])
        FoundationJoints.__init__(self)
