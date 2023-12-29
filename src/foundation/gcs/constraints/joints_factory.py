from foundation.gcs.constraints.constraints3d import (
    AnchorComponent,
    PlaneToPlaneCoincid,
    PointWithOrientationCoincidence,
    SameX3D,
    SameY3D,
    SameZ3D,
    SameRoll3D,
    SamePitch3D,
    SameYaw3D,
)
from foundation.types.component import Component
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from foundation.types.assembly import Assembly


class JointFactory:
    """Easily create joints for assembly of multiple components"""

    def __init__(self, assy: "Assembly"):
        self.assy = assy

    def anchor_component(self, component: Component):
        j = AnchorComponent(component)
        self.assy.add_joint(j)

    def plane_coincidence(self, plane1, plane2, opposite=False):
        """return a joint that will match the two planes"""
        j = PlaneToPlaneCoincid(plane1, plane2, opposite=opposite)
        self.assy.add_joint(j)

    def axis_coincidence(self, axis1, axis2):
        pass

    def point_with_orientation_coincidence(self, point1, point2):
        j = PointWithOrientationCoincidence(point1, point2)
        self.assy.add_joint(j)

    def same_x(self, point1, point2):
        j = SameX3D(point1, point2)
        self.assy.add_joint(j)

    def same_y(self, point1, point2):
        j = SameY3D(point1, point2)
        self.assy.add_joint(j)

    def same_z(self, point1, point2):
        j = SameZ3D(point1, point2)
        self.assy.add_joint(j)

    def same_pitch(self, point1, point2):
        j = SamePitch3D(point1, point2)
        self.assy.add_joint(j)

    def same_yaw(self, point1, point2):
        j = SameYaw3D(point1, point2)
        self.assy.add_joint(j)

    def same_roll(self, point1, point2):
        j = SameRoll3D(point1, point2)
        self.assy.add_joint(j)

    def point_plane_coincidence(self, point, plane):
        pass

    def point_axis_coincidence(self, point, axis):
        pass
