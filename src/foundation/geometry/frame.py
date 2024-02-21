from foundation.types.node import Node, Orphan
from foundation.types.node_interface import NodeInterface
import numpy as np
from foundation.types.point_3d import Point3DWithOrientation
from foundation.geometry.transform3d import RotationMatrix, TransformMatrix
from typing import Union, List


class Frame(Orphan):
    """a FrameInterface
    describes a 3D frame (position and orientation) in space.
    The head node of any assembly or comonent is a FrameInterface( see OriginFrame)

    """

    def __init__(
        self,
        top_frame: "Frame",
        name: str,
        transform: TransformMatrix,
    ):
        Orphan.__init__(self)
        assert type(transform) == TransformMatrix
        self.top_frame = top_frame
        self.transform = transform
        self.point_with_orientation = Point3DWithOrientation.from_transform(
            self.transform
        )
        self.name = name

        if top_frame is not None:
            self.register_child(top_frame)
            top_frame.compute_params()
        self.compute_params()
        self.name = name
        self.top_frame = top_frame
        self.transform = transform

    def get_name(self) -> str:
        return self.name

    def get_parent_name(self):
        if self.top_frame is not None:
            return self.top_frame.get_name()
        else:
            return None

    def get_frame_coordinates(self):
        return self.transform.get_position()

    def get_x_axis(self, local=True):
        """return a vector orthogonal to the plane ->
        this is the 1st vector of the frame."""
        if local:
            return np.array([1.0, 0.0, 0.0])
        else:
            self.get_frame_coordinates()[0]

    def get_y_axis(self, local=True):
        """return a vector orthogonal to the plane ->
        this is the 2nd vector of the frame."""
        if local:
            return np.array([0.0, 1.0, 0.0])
        else:
            return self.get_frame_coordinates()[1]

    def get_z_axis(self, local=True):
        """return a vector orthogonal to the plane ->
        this is the 3rd vector of the frame."""
        if local:
            return np.array([0.0, 0.0, 1.0])
        else:
            return self.get_frame_coordinates()[2]

    def get_transform(self):
        """return the transform of the frame (from the parent frame)"""
        return self.transform

    def get_transform_and_top_origin_frame(self):
        """recursively looks at top frame to see if there is an
        origin frame. If origin frame is found, returns the transform to
        the frame (composition of transforms)"""

        final_tf = np.eye(4, dtype="float")
        frame = self
        while type(frame) != OriginFrame:
            final_tf = frame.transform.concat(final_tf)
            frame = self.top_frame
        return frame, final_tf

    def get_position_and_quaternions(self):
        """return the position of the frame (from the parent frame)"""
        # position is first 3 value, quaternion is the last 4
        pos, quat = self.transform.to_position_quaternion()
        position = {x: float(pos[i]) for i, x in enumerate(["x", "y", "z"])}
        quaternion = {x: float(quat[i]) for i, x in enumerate(["w", "x", "y", "z"])}
        return {"position": position, "quaternion": quaternion}

    def get_translated_frame(self, name, translation):
        """Translation is a 3d vector (numpy array)"""
        top_tf = self.get_transform()
        tf = TransformMatrix.get_from_position(translation).concat(top_tf)
        return Frame(self, name, tf)

    def get_rotated_frame(self, name: str, rot_mat: RotationMatrix):
        """Rotation is a 3x3 matrix (numpy array)"""
        top_tf = self.get_transform()
        tf = TransformMatrix.get_from_rotation_matrix(rot_mat).concat(top_tf)
        return Frame(self, name, tf)

    def get_rotate_then_translate_frame(self, name, translation, rotation):
        # Not given the mat dot product applied to (x, y , z, 1)
        # the point is always rotated and then translated.
        top_tf = self.get_transform()
        tf = TransformMatrix.from_rotation_matrix_and_position(
            rotation, translation
        ).concat(top_tf)
        return Frame(self, name, tf)

    def get_rotated_frame_from_axis(self, axis, angle, name):
        """return the rotated frame rotated by given axis and angle"""
        rot_mat = RotationMatrix.from_axis_angle(axis, angle)
        return self.get_rotated_frame(name=name, rot_mat=rot_mat)

    def compute_params(self):
        p, q = self.transform.to_position_quaternion()
        self.params = {
            "position": list(p),
            "quaternion": list(q),
            "name": self.name,
            "top_frame_id": self.top_frame.id if self.top_frame is not None else None,
            "deps": [c.id for c in self.children],
            ## could remove only for debug
            "id": self.id,
            "parent_name": self.top_frame.name if self.top_frame is not None else None,
        }


class OriginFrame(Frame):
    """The origin Frame has no parent"""

    def __init__(self):
        super().__init__(
            top_frame=None, name="origin", transform=TransformMatrix.get_identity()
        )

    def to_default_frame(self, top_frame, component_id, tf):
        """When adding a part to an assembly its originframe will be converted to a
        default frame"""

        self.top_frame = top_frame
        self.name = self.name + f"_{component_id}"
        self.transform = tf
        self.compute_params()

        for child in self.children:
            if type(child) in [Frame, OriginFrame]:
                child.compute_params()
