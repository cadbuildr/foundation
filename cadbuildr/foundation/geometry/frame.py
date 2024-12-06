from cadbuildr.foundation.types.node import Node
from cadbuildr.foundation.types.node_children import NodeChildren
from cadbuildr.foundation.types.node_interface import NodeInterface
import numpy as np
from numpy import ndarray
from cadbuildr.foundation.geometry.transform3d import RotationMatrix, TransformMatrix
from cadbuildr.foundation.types.parameters import (
    StringParameter,
    BoolParameter,
    cast_to_string_parameter,
    cast_to_bool_parameter,
    UnCastString,
    UnCastBool,
)
from typing import Union, Optional
from cadbuildr.foundation.exceptions import NotAUnitVectorException, GeometryException


class FrameChildren(NodeChildren):
    top_frame: "Frame"  # Frame that is the parent of the current frame, if None it is the origin frame
    name: StringParameter
    display: BoolParameter


class Frame(Node):
    """a FrameInterface
    describes a 3D frame (position and orientation) in space.
    """

    children_class = FrameChildren

    def __init__(
        self,
        top_frame: Union["Frame", None],
        name: str,
        transform: TransformMatrix,
        display: UnCastBool = False,
    ):
        Node.__init__(self)
        assert type(transform) == TransformMatrix
        if top_frame is not None:
            self.children.set_top_frame(top_frame)
        self.children.set_name(cast_to_string_parameter(name))
        self.children.set_display(cast_to_bool_parameter(display))
        self.transform = transform

        # shortcuts
        self.top_frame = top_frame
        self.name = self.children._children["name"]

        if top_frame is not None:
            top_frame.compute_params()
        self.compute_params()
        self.transform = transform

    def get_name(self) -> str:
        return self.name.value

    def get_parent_name(self) -> str | None:
        if self.top_frame is not None:
            return self.top_frame.get_name()
        else:
            return None

    def __str__(self) -> str:
        return (
            "Frame : "
            + self.get_name()
            + " with parent : "
            + str(self.get_parent_name())
            + " and transform : "
            + str(self.transform)
        )

    def get_frame_coordinates(self) -> ndarray:
        return self.transform.get_position()

    def get_x_axis(self, local: bool = True) -> ndarray:
        """return a vector orthogonal to the plane ->
        this is the 1st vector of the frame."""
        if local:
            return np.array([1.0, 0.0, 0.0])
        else:
            return self.get_frame_coordinates()[0]

    def get_y_axis(self, local: bool = True) -> ndarray:
        """return a vector orthogonal to the plane ->
        this is the 2nd vector of the frame."""
        if local:
            return np.array([0.0, 1.0, 0.0])
        else:
            return self.get_frame_coordinates()[1]

    def get_z_axis(self, local: bool = True) -> ndarray:
        """return a vector orthogonal to the plane ->
        this is the 3rd vector of the frame."""
        if local:
            return np.array([0.0, 0.0, 1.0])
        else:
            return self.get_frame_coordinates()[2]

    def get_transform(self) -> TransformMatrix:
        """return the transform of the frame (from the parent frame)"""
        return self.transform

    def set_transform(self, tf: TransformMatrix):
        self.transform = tf

    def get_position_and_quaternions(self) -> dict[str, dict[str, float]]:
        """return the position of the frame (from the parent frame)"""
        # position is first 3 value, quaternion is the last 4
        pos, quat = self.transform.to_position_quaternion()
        position = {x: float(pos[i]) for i, x in enumerate(["x", "y", "z"])}
        quaternion = {x: float(quat[i]) for i, x in enumerate(["w", "x", "y", "z"])}
        return {"position": position, "quaternion": quaternion}

    def get_translated_frame(self, name: str, translation: ndarray) -> "Frame":
        """Translation is a 3d vector (numpy array)"""
        tf = TransformMatrix.get_from_position(translation)
        return Frame(self, name, tf)

    def get_rotated_frame(self, name: str, rot_mat: RotationMatrix) -> "Frame":
        """Rotation is a 3x3 matrix (numpy array)"""
        tf = TransformMatrix.get_from_rotation_matrix(rot_mat)
        return Frame(self, name, tf)

    def get_rotate_then_translate_frame(
        self, name: str, translation: ndarray, rotation: RotationMatrix
    ) -> "Frame":
        # Not given the mat dot product applied to (x, y , z, 1)
        # the point is always rotated and then translated.
        top_tf = self.get_transform()
        tf = TransformMatrix.from_rotation_matrix_and_position(
            rotation, translation
        ).concat(top_tf)
        return Frame(self, name, tf)

    def get_rotated_frame_from_axis(
        self, axis: ndarray, angle: float, name: str
    ) -> "Frame":
        """return the rotated frame rotated by given axis and angle"""
        rot_mat = RotationMatrix.from_axis_angle(axis, angle)
        return self.get_rotated_frame(name=name, rot_mat=rot_mat)

    def from_3dpoint_and_xy_axes(
        self, name: str, point: ndarray, x_axis: ndarray, y_axis: ndarray
    ) -> "Frame":
        """Return a frame from a 3d point and 2 orthogonal vectors
        the point is the origin of the frame
        the x_axis is the first vector of the frame
        the y_axis is the second vector of the frame
        """
        # Check if the vectors are unit vectors
        if not np.isclose(np.linalg.norm(x_axis), 1.0):
            raise NotAUnitVectorException(x_axis, "x_axis")
        if not np.isclose(np.linalg.norm(y_axis), 1.0):
            raise NotAUnitVectorException(y_axis, "y_axis")

        # Check if the vectors are orthogonal
        if not np.isclose(np.dot(x_axis, y_axis), 0.0):
            raise GeometryException("x_axis and y_axis are not orthogonal")

        z_axis = np.cross(x_axis, y_axis)
        rot_mat = RotationMatrix(np.array([x_axis, y_axis, z_axis]).T)
        tf = TransformMatrix.from_rotation_matrix_and_position(rot_mat, point)
        return Frame(self, name, tf)

    def from_xdir_and_normal(
        self, name: str, point: ndarray, x_dir: ndarray, normal: ndarray
    ) -> "Frame":
        """Return a frame from a 3D point, an x-direction vector, and a normal vector.
        The point is the origin of the frame.
        The x_dir is the first vector of the frame (x-axis).
        The normal is the normal vector to the plane formed by x and y axes (z-axis).
        """
        # Normalize the vectors
        x_dir_norm = np.linalg.norm(x_dir)
        normal_norm = np.linalg.norm(normal)
        x_dir_unit = x_dir / x_dir_norm
        normal_unit = normal / normal_norm

        # Check if the vectors are unit vectors
        if not np.isclose(x_dir_norm, 1.0):
            raise NotAUnitVectorException(x_dir, "x_dir")
        if not np.isclose(normal_norm, 1.0):
            raise NotAUnitVectorException(normal, "normal")

        # Check if the vectors are orthogonal
        if not np.isclose(np.dot(x_dir_unit, normal_unit), 0.0):
            raise GeometryException("x_dir and normal are not orthogonal")

        # Compute y_axis as the cross product of normal and x_dir
        y_axis = np.cross(normal_unit, x_dir_unit)
        y_axis_unit = y_axis / np.linalg.norm(y_axis)

        # Form the rotation matrix
        rot_mat = RotationMatrix(np.array([x_dir_unit, y_axis_unit, normal_unit]).T)

        # Create the TransformMatrix
        tf = TransformMatrix.from_rotation_matrix_and_position(rot_mat, point)

        # Return the new Frame
        return Frame(self, name, tf)

    def compute_params(self):
        p, q = self.transform.to_position_quaternion()
        self.params = {
            "position": list(p),
            "quaternion": list(q),
        }

    def change_top_frame(
        self,
        new_top_frame: "Frame",
        new_name: Optional[UnCastString] = None,
        new_tf=None,
    ):
        self.children.set_top_frame(new_top_frame)
        if new_name is not None:
            self.children.set_name(cast_to_string_parameter(new_name))

        if new_tf is not None:
            self.transform = new_tf
        # shortcuts update
        self.top_frame = self.children._children["top_frame"]
        self.name = self.children._children["name"]

        self.compute_params()

    @staticmethod
    def make_origin_frame(display: UnCastBool = False) -> "Frame":
        return Frame(None, "origin", TransformMatrix.get_identity(), display)


FrameChildren.__annotations__["top_frame"] = Frame
FrameChildren.__annotations__["name"] = StringParameter
