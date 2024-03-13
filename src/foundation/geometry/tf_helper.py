import numpy as np
from numpy import ndarray
from foundation.geometry.transform3d import RotationMatrix, TransformMatrix


def get_rotation_matrix(axis, angle):
    """axis is a 3d vector (numpy array)"""
    return RotationMatrix.from_axis_angle(axis, angle, normalized=True)


class TFHelper:
    """Helper to make working with transformation matrices easier."""

    def __init__(self):
        self.set_init()

    def set_init(self):
        self.tf = TransformMatrix.get_identity()

    def set_tf(self, tf: TransformMatrix):
        self.tf = tf

    def get_tf(self) -> TransformMatrix:
        return self.tf

    def translate(self, translation: ndarray, rotate: bool = False) -> "TFHelper":
        """Translation is a 3d vector (numpy array)"""
        translation = np.array(translation, dtype="float")
        if rotate:
            self.rotate_and_translate(RotationMatrix.get_identity(), translation)
        else:
            self.tf.matrix[:3, 3] += translation
        return self

    def translate_x(self, x: float, rotate: bool = False) -> "TFHelper":
        return self.translate([float(x), 0.0, 0.0], rotate)

    def translate_y(self, y: float, rotate: bool = False) -> "TFHelper":
        return self.translate([0.0, float(y), 0.0], rotate)

    def translate_z(self, z: float, rotate: bool = False) -> "TFHelper":
        return self.translate([0.0, 0.0, float(z)], rotate)

    def rotate(
        self, axis: ndarray = np.array([0.0, 0.0, 1.0]), angle: float = np.pi / 2
    ) -> "TFHelper":
        """axis is a 3d vector (numpy array) and angle is a float"""
        axis = np.array(axis, dtype="float")
        rotation_matrix = RotationMatrix.from_axis_angle(axis, angle, normalized=True)
        self.rotate_and_translate(rotation_matrix, [0.0, 0.0, 0.0])
        return self

    def rotate_and_translate(
        self, rotation_matrix: RotationMatrix, translation: ndarray
    ) -> "TFHelper":
        """using a rotation_matrix and translation, update the tf"""
        translation = np.array(translation, dtype="float")
        pq_transform = TransformMatrix.from_rotation_matrix_and_position(
            rotation_matrix, translation
        )
        self.tf = pq_transform.concat(self.tf)
        return self
