from foundation.types.node import Node
from foundation.types.node_children import NodeChildren
from foundation.types.node_interface import NodeInterface
import numpy as np
from numpy import ndarray
from foundation.geometry.transform3d import RotationMatrix, TransformMatrix
from foundation.types.parameters import (
    StringParameter,
    BoolParameter,
    cast_to_string_parameter,
    cast_to_bool_parameter,
    UnCastString,
    UnCastBool,
)


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
        top_frame: "Frame",  # Union[Frame, None
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
        self.name = name

        if top_frame is not None:
            top_frame.compute_params()
        self.compute_params()
        self.name = name
        self.top_frame = top_frame
        self.transform = transform

    def get_name(self) -> str:
        return self.name

    def get_parent_name(self) -> str | None:
        if self.top_frame is not None:
            return self.top_frame.get_name()
        else:
            return None

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

    def get_position_and_quaternions(self) -> dict[str, dict[str, float]]:
        """return the position of the frame (from the parent frame)"""
        # position is first 3 value, quaternion is the last 4
        pos, quat = self.transform.to_position_quaternion()
        position = {x: float(pos[i]) for i, x in enumerate(["x", "y", "z"])}
        quaternion = {x: float(quat[i]) for i, x in enumerate(["w", "x", "y", "z"])}
        return {"position": position, "quaternion": quaternion}

    def get_translated_frame(self, name: str, translation: ndarray) -> "Frame":
        """Translation is a 3d vector (numpy array)"""
        top_tf = self.get_transform()
        tf = TransformMatrix.get_from_position(translation).concat(top_tf)
        return Frame(self, name, tf)

    def get_rotated_frame(self, name: str, rot_mat: RotationMatrix) -> "Frame":
        """Rotation is a 3x3 matrix (numpy array)"""
        top_tf = self.get_transform()
        tf = TransformMatrix.get_from_rotation_matrix(rot_mat).concat(top_tf)
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

    def compute_params(self):
        p, q = self.transform.to_position_quaternion()
        self.params = {
            "position": list(p),
            "quaternion": list(q),
        }

    def change_top_frame(self, new_top_frame: "Frame", new_name: UnCastString, new_tf):
        self.children.set_top_frame(new_top_frame)
        self.children.set_name(cast_to_string_parameter(new_name))

        self.transform = new_tf
        # shortcuts update
        self.top_frame = self.children._children["top_frame"]
        self.name = self.children._children["name"]

        self.compute_params()

    @staticmethod
    def make_origin_frame():
        return Frame(None, "origin", TransformMatrix.get_identity())


# class OriginFrame(Frame):
#     """The origin Frame has no parent"""

#     def __init__(self):
#         super().__init__(
#             top_frame=None, name="origin", transform=TransformMatrix.get_identity()
#         )

#     def to_default_frame(
#         self, top_frame: "Frame", component_id, tf
#     ):  # TODO define type for component_id and tf
#         """When adding a part to an assembly its frame will be converted to a
#         default frame"""
#         top_frame.parents.append(self)
#         self.top_frame = top_frame
#         self.name = self.name + f"_{component_id}"

#         self.transform = tf
#         self.compute_params()


FrameChildren.__annotations__["top_frame"] = Frame
FrameChildren.__annotations__["name"] = StringParameter
