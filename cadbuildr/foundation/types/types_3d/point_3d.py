from cadbuildr.foundation.types.node import Node
from cadbuildr.foundation.types.parameters import (
    UnCastFloat,
    cast_to_float_parameter,
    FloatParameter,
)
from cadbuildr.foundation.geometry.transform3d import TransformMatrix
from cadbuildr.foundation.types.node_children import NodeChildren
import numpy as np


class Point3DChildren(NodeChildren):
    x: FloatParameter
    y: FloatParameter
    z: FloatParameter


class Point3D(Node):
    """A 3D point in space"""

    children_class = Point3DChildren

    def __init__(self, x: UnCastFloat, y: UnCastFloat, z: UnCastFloat):
        Node.__init__(self)

        self.children.set_x(cast_to_float_parameter(x))
        self.children.set_y(cast_to_float_parameter(y))
        self.children.set_z(cast_to_float_parameter(z))

        # shortcuts
        self.x = self.children.x
        self.y = self.children.y
        self.z = self.children.z

        self.params = {}

    def __str__(self):
        return f"Point3D({self.x.value}, {self.y.value}, {self.z.value})"

    def __repr__(self):
        return self.__str__()

    def __sub__(self, other: "Point3D") -> "Point3D":
        """Subtract another Point3D from this Point3D and return the result as a new Point3D."""
        if not isinstance(other, Point3D):
            raise ValueError("The operand must be an instance of Point3D.")

        x_diff = self.x.value - other.x.value
        y_diff = self.y.value - other.y.value
        z_diff = self.z.value - other.z.value

        return Point3D(x_diff, y_diff, z_diff)

    def to_array(self) -> np.ndarray:
        """Convert the Point3D to a NumPy array."""
        return np.array([self.x.value, self.y.value, self.z.value])


class Point3DWithOrientationChildren(NodeChildren):
    roll: FloatParameter
    pitch: FloatParameter
    yaw: FloatParameter
    point: Point3D


class Point3DWithOrientation(Node):
    """A 3D points with orientation ( roll, pitch, yaw)"""

    def __init__(
        self, p: Point3D, roll: UnCastFloat, pitch: UnCastFloat, yaw: UnCastFloat
    ):

        Node.__init__(self)

        self.children.set_roll(cast_to_float_parameter(roll))
        self.children.set_pitch(cast_to_float_parameter(pitch))
        self.children.set_yaw(cast_to_float_parameter(yaw))
        self.children.set_point(p)

        # shortcuts
        self.roll = self.children.roll
        self.pitch = self.children.pitch
        self.yaw = self.children.yaw
        self.point = self.children.point
        self.params = {}
        self.name = "v_" + str(self.id)

    @staticmethod
    def from_transform(tf: TransformMatrix):
        rot_mat = tf.get_rotation()
        roll, pitch, yaw = rot_mat.to_euler_angles()
        xyz = tf.get_position()

        p = Point3D(xyz[0], xyz[1], xyz[2])
        return Point3DWithOrientation(p, roll, pitch, yaw)


Point3DChildren.__annotations__["x"] = FloatParameter
Point3DChildren.__annotations__["y"] = FloatParameter
Point3DChildren.__annotations__["z"] = FloatParameter

Point3DWithOrientationChildren.__annotations__["roll"] = FloatParameter
Point3DWithOrientationChildren.__annotations__["pitch"] = FloatParameter
Point3DWithOrientationChildren.__annotations__["yaw"] = FloatParameter
Point3DWithOrientationChildren.__annotations__["point"] = Point3D
