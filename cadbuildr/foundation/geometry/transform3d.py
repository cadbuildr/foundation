# File to remove dependenct on pytransform3d
import numpy as np
from numpy import ndarray
from cadbuildr.foundation.exceptions import (
    NaNInMatrixException,
    TraceLessThanZeroException,
    ZeroQuaternionNormException,
    ZeroLengthVectorException,
    InvalidParameterTypeException,
)


class RotationMatrix:
    def __init__(self, matrix: ndarray):
        self.matrix = matrix

    @staticmethod
    def get_identity() -> "RotationMatrix":
        return RotationMatrix(np.eye(3, dtype="float"))

    @staticmethod
    def from_axis_angle(axis: ndarray, angle: float) -> "RotationMatrix":
        """Create the rotation matrix from an axis and an angle that rotate around that axis
        if normalized, we normalize the axis ( otherwise will multiple angle by the norm if not 1)
        """
        if np.linalg.norm(axis) == 0:
            ZeroLengthVectorException(axis, "axis")
        axis = axis / np.linalg.norm(axis)
        x, y, z = axis
        c = np.cos(angle)
        s = np.sin(angle)

        # first row
        r00 = c + x**2 * (1 - c)
        r01 = x * y * (1 - c) - z * s
        r02 = x * z * (1 - c) + y * s

        # second row
        r10 = y * x * (1 - c) + z * s
        r11 = c + y**2 * (1 - c)
        r12 = y * z * (1 - c) - x * s

        # third row
        r20 = z * x * (1 - c) - y * s
        r21 = z * y * (1 - c) + x * s
        r22 = c + z**2 * (1 - c)

        return RotationMatrix(
            np.array(
                [
                    [r00, r01, r02],
                    [r10, r11, r12],
                    [r20, r21, r22],
                ]
            )
        )

    @staticmethod
    def from_quaternion(
        quaternion: tuple[float, float, float, float] | ndarray
    ) -> "RotationMatrix":
        if not isinstance(quaternion, (tuple, np.ndarray)) or len(quaternion) != 4:
            raise InvalidParameterTypeException(
                "quaternion", quaternion, "tuple or ndarray of length 4"
            )

        q0, q1, q2, q3 = quaternion

        # first row
        r00 = 1 - 2 * q2 * q2 - 2 * q3 * q3
        r01 = 2 * q1 * q2 - 2 * q0 * q3
        r02 = 2 * q1 * q3 + 2 * q0 * q2

        # second row
        r10 = 2 * q1 * q2 + 2 * q0 * q3
        r11 = 1 - 2 * q1 * q1 - 2 * q3 * q3
        r12 = 2 * q2 * q3 - 2 * q0 * q1

        # third row
        r20 = 2 * q1 * q3 - 2 * q0 * q2
        r21 = 2 * q2 * q3 + 2 * q0 * q1
        r22 = 1 - 2 * q1 * q1 - 2 * q2 * q2

        return RotationMatrix(
            np.array([[r00, r01, r02], [r10, r11, r12], [r20, r21, r22]])
        )

    # TODO define angles type
    @staticmethod
    def from_euler_angles(
        angles: tuple[float, float, float] | ndarray | list[float]
    ) -> "RotationMatrix":
        if not isinstance(angles, (tuple, np.ndarray, list)) or len(angles) != 3:
            raise InvalidParameterTypeException(
                "angles", angles, "tuple or ndarray of length 3"
            )

        row, pitch, yaw = angles

        crow = np.cos(row)
        cpitch = np.cos(pitch)
        cyaw = np.cos(yaw)

        srow = np.sin(row)
        spitch = np.sin(pitch)
        syaw = np.sin(yaw)

        # first row
        r00 = cyaw * cpitch
        r01 = cyaw * spitch * srow - syaw * crow
        r02 = cyaw * spitch * crow + syaw * srow

        # second row
        r10 = syaw * cpitch
        r11 = syaw * spitch * srow + cyaw * crow
        r12 = syaw * spitch * crow - cyaw * srow

        # third row
        r20 = -spitch
        r21 = cpitch * srow
        r22 = cpitch * crow

        return RotationMatrix(
            np.array([[r00, r01, r02], [r10, r11, r12], [r20, r21, r22]])
        )

    def to_quaternion(self) -> np.ndarray:
        """Convert the rotation matrix to a quaternion."""
        M = self.matrix
        q = np.empty(4)
        trace = M[0, 0] + M[1, 1] + M[2, 2]

        if trace > 0.0:
            s = 0.5 / np.sqrt(trace + 1.0)
            q[0] = 0.25 / s
            q[1] = (M[2, 1] - M[1, 2]) * s
            q[2] = (M[0, 2] - M[2, 0]) * s
            q[3] = (M[1, 0] - M[0, 1]) * s
        else:
            if M[0, 0] > M[1, 1] and M[0, 0] > M[2, 2]:
                s = 2.0 * np.sqrt(1.0 + M[0, 0] - M[1, 1] - M[2, 2])
                q[0] = (M[2, 1] - M[1, 2]) / s
                q[1] = 0.25 * s
                q[2] = (M[0, 1] + M[1, 0]) / s
                q[3] = (M[0, 2] + M[2, 0]) / s
            elif M[1, 1] > M[2, 2]:
                s = 2.0 * np.sqrt(1.0 + M[1, 1] - M[0, 0] - M[2, 2])
                q[0] = (M[0, 2] - M[2, 0]) / s
                q[1] = (M[0, 1] + M[1, 0]) / s
                q[2] = 0.25 * s
                q[3] = (M[1, 2] + M[2, 1]) / s
            else:
                s = 2.0 * np.sqrt(1.0 + M[2, 2] - M[0, 0] - M[1, 1])
                q[0] = (M[1, 0] - M[0, 1]) / s
                q[1] = (M[0, 2] + M[2, 0]) / s
                q[2] = (M[1, 2] + M[2, 1]) / s
                q[3] = 0.25 * s

        norm = np.linalg.norm(q)
        if norm == 0:
            raise ZeroQuaternionNormException()
        return q / norm

    def to_axis_angle(self) -> tuple[ndarray, float]:
        # return a 3d vector and a scalar
        angle = np.arccos((np.trace(self.matrix) - 1) / 2)

        if np.sin(angle) == 0:
            return np.array([1.0, 0.0, 0.0]), 0
        # unit vector
        x = (self.matrix[2, 1] - self.matrix[1, 2]) / (2 * np.sin(angle))
        y = (self.matrix[0, 2] - self.matrix[2, 0]) / (2 * np.sin(angle))
        z = (self.matrix[1, 0] - self.matrix[0, 1]) / (2 * np.sin(angle))

        return np.array([x, y, z]), angle

    def to_euler_angles(self) -> ndarray:
        # return a 3d vector
        row = np.arctan2(self.matrix[2, 1], self.matrix[2, 2])
        pitch = np.arctan2(
            -self.matrix[2, 0], np.sqrt(self.matrix[2, 1] ** 2 + self.matrix[2, 2] ** 2)
        )
        yaw = np.arctan2(self.matrix[1, 0], self.matrix[0, 0])

        return np.array([row, pitch, yaw])


class TransformMatrix:
    def __init__(self, matrix: ndarray):
        self.matrix = matrix

    def __str__(self) -> str:
        return str(self.matrix)

    def concat(self, B2C: "TransformMatrix"):
        """Considering self as A2B, return A2C"""
        return TransformMatrix(np.dot(B2C.matrix, self.matrix))

    def concat_in_place(self, other: "TransformMatrix"):
        # return a TransformMatrix
        self.matrix = self.concat(other).matrix

    def to_position_quaternion(self) -> tuple[ndarray, ndarray]:
        """Return a tuple (position, quaternion)
        position is a 3d vector
        quaternion is a 4d vector
        """

        position = self.matrix[:3, 3]
        rot_mat = RotationMatrix(self.matrix[:3, :3])
        quaternion = rot_mat.to_quaternion()
        return position, quaternion

    def get_position(self) -> ndarray:
        return self.matrix[:3, 3]

    def get_rotation(self) -> RotationMatrix:
        return RotationMatrix(self.matrix[:3, :3])

    def get_position_and_euler(self) -> tuple[ndarray, ndarray]:
        return self.matrix[:3, 3], self.get_rotation().to_euler_angles()

    def inverse(self) -> "TransformMatrix":
        # return a TransformMatrix
        return TransformMatrix(np.linalg.inv(self.matrix))

    @staticmethod
    def get_identity() -> "TransformMatrix":
        return TransformMatrix(np.eye(4, dtype="float"))

    @staticmethod
    def get_from_position(translation: list[float] | ndarray) -> "TransformMatrix":
        """x y z array as input"""
        if isinstance(translation, list):
            translation = np.array(translation, dtype="float")
        if translation.shape != (3,):
            raise InvalidParameterTypeException(
                "translation",
                translation,
                "a list of 3 floats or a numpy array of shape (3,)",
            )

        matrix = np.eye(4, dtype="float")
        matrix[:3, 3] = translation
        return TransformMatrix(matrix)

    @staticmethod
    def get_from_euler_angles(angles: list[float] | ndarray) -> "TransformMatrix":
        """row, pitch, yaw array as input"""
        if isinstance(angles, list):
            angles = np.array(angles, dtype="float")
        if angles.shape != (3,):
            raise InvalidParameterTypeException(
                "angles", angles, "a list of 3 floats or a numpy array of shape (3,)"
            )

        rot_mat = RotationMatrix.from_euler_angles(angles)
        matrix = np.eye(4, dtype="float")
        matrix[:3, :3] = rot_mat.matrix
        return TransformMatrix(matrix)

    @staticmethod
    def get_from_quaternion(quaternion: list[float] | ndarray) -> "TransformMatrix":
        """q0, q1, q2, q3 array as input"""
        if isinstance(quaternion, list):
            quaternion = np.array(quaternion, dtype="float")
        if quaternion.shape != (4,):
            raise InvalidParameterTypeException(
                "quaternion",
                quaternion,
                "a list of 4 floats or a numpy array of shape (4,)",
            )
        rot_mat = RotationMatrix.from_quaternion(quaternion)
        matrix = np.eye(4, dtype="float")
        matrix[:3, :3] = rot_mat.matrix
        return TransformMatrix(matrix)

    @staticmethod
    def from_rotation_matrix_and_position(
        rot_mat: RotationMatrix, position: list[float] | ndarray
    ) -> "TransformMatrix":
        if not isinstance(position, (list, np.ndarray)) or len(position) != 3:
            raise InvalidParameterTypeException("position", position, "3d vector")
        if isinstance(position, list):
            position = np.array(position, dtype="float")
        if position.shape != (3,):
            raise InvalidParameterTypeException("position", position, "3d vector")
        matrix = np.eye(4, dtype="float")
        matrix[:3, :3] = rot_mat.matrix
        matrix[:3, 3] = position
        return TransformMatrix(matrix)

    @staticmethod
    def get_from_rotation_matrix(rot_mat: RotationMatrix) -> "TransformMatrix":
        matrix = np.eye(4, dtype="float")
        matrix[:3, :3] = rot_mat.matrix
        return TransformMatrix(matrix)
