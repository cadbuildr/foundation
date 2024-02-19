from foundation.types.node import Orphan
from foundation.types.parameters import (
    UnCastFloat,
    cast_to_float_parameter,
)
from foundation.geometry.transform3d import TransformMatrix


class Point3D(Orphan):
    """A 3D point in space. Can be attached to many types of Parents -> Orphan"""

    def __init__(self, x: UnCastFloat, y: UnCastFloat, z: UnCastFloat):
        self.x = cast_to_float_parameter(x)
        self.y = cast_to_float_parameter(y)
        self.z = cast_to_float_parameter(z)
        Orphan.__init__(self)
        self.x.attach_to_parent(self)
        self.y.attach_to_parent(self)
        self.z.attach_to_parent(self)
        self.params = {
            "n_x": self.x.id,
            "n_y": self.y.id,
            "n_z": self.z.id,
        }


class Point3DWithOrientation(Orphan):
    """A 3D points with orientation ( roll, pitch, yaw)"""

    def __init__(
        self, p: Point3D, roll: UnCastFloat, pitch: UnCastFloat, yaw: UnCastFloat
    ):
        self.roll = cast_to_float_parameter(roll)
        self.pitch = cast_to_float_parameter(pitch)
        self.yaw = cast_to_float_parameter(yaw)
        Orphan.__init__(self)
        self.roll.attach_to_parent(self)
        self.pitch.attach_to_parent(self)
        self.yaw.attach_to_parent(self)
        self.point = p
        self.point.attach_to_parent(self)
        self.params = {
            "n_roll": self.roll.id,
            "n_pitch": self.pitch.id,
            "n_yaw": self.yaw.id,
            "n_point": self.point.id,
        }
        self.name = "v_" + str(self.id)

    @staticmethod
    def from_transform(tf: TransformMatrix):
        rot_mat = tf.get_rotation()
        roll, pitch, yaw = rot_mat.to_euler_angles()
        xyz = tf.get_position()

        p = Point3D(xyz[0], xyz[1], xyz[2])
        return Point3DWithOrientation(p, roll, pitch, yaw)
