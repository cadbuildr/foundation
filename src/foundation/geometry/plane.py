from foundation.types.node import Node
from foundation.types.node_interface import NodeInterface
from foundation.types.node_children import NodeChildren
from foundation.geometry.frame import Frame
import numpy as np
from numpy import ndarray
from foundation.types.parameters import StringParameter, cast_to_string_parameter


class PlaneChildren(NodeChildren):
    frame: "Frame"
    name: StringParameter


class PlaneFromFrame(Node):
    parent_types = []
    children_class = PlaneChildren

    def __init__(self, frame: Frame, name: str):
        Node.__init__(self)
        self.children.set_frame(frame)
        self.children.set_name(cast_to_string_parameter(name))
        self.frame = frame
        self.name = name
        self.params = {}

    def get_x_axis(self, local: bool = True) -> np.ndarray:
        """return a vector orthogonal to the plane ->
        this is the 1st vector of the frame."""
        return self.frame.get_x_axis(local)

    def get_y_axis(self, local: bool = True) -> np.ndarray:
        """return a vector orthogonal to the plane ->
        this is the 2nd vector of the frame."""
        return self.frame.get_y_axis(local)

    def get_normal(self, local: bool = True) -> np.ndarray:
        """return a vector orthogonal to the plane ->
        this is the 3rd vector of the frame."""
        return self.frame.get_z_axis(local)

    def get_parallel_plane(self, distance: float, name: str) -> "PlaneFromFrame":
        """return a plane parallel to the given plane at the given distance
        distance can be negative, it really is a translation in the direction of the normal
        """

        normal = self.get_normal()
        translated_frame = self.frame.get_translated_frame(
            name="f" + name, translation=normal * distance
        )
        return PlaneFromFrame(translated_frame, name)

    def get_angle_plane_from_axis(
        self, axis: ndarray, angle: float, name: str
    ) -> "PlaneFromFrame":
        """return the angle between the plane and the given axis"""
        # check_axis_is_on_plane(axis, plane) TODO
        rotated_frame = self.frame.get_rotated_frame_from_axis(axis, angle, "f" + name)
        return PlaneFromFrame(rotated_frame, name)


class PlaneFactory:
    def __init__(self):
        self.counter = 0

    def _get_name(self, name: str | None) -> str:
        if name is None:
            name = "plane_" + str(self.counter)
        self.counter += 1
        return name

    def get_parallel_plane(
        self, plane: PlaneFromFrame, distance: float, name: str | None = None
    ) -> PlaneFromFrame:
        return plane.get_parallel_plane(distance, self._get_name(name))

    def get_angle_plane_from_axis(
        self,
        plane: PlaneFromFrame,
        axis: ndarray,
        angle: float,
        name: str | None = None,
    ) -> PlaneFromFrame:
        """return a plane rotated around the given axis by the given angle
        axis must be on the frame"""

        return plane.get_angle_plane_from_axis(axis, angle, self._get_name(name))

    def get_xy_plane_from_frame(
        self, frame: Frame, name: str | None = None
    ) -> PlaneFromFrame:
        # xy is the default plane from the frame ( no need for any rotation)
        return PlaneFromFrame(frame, self._get_name(name))

    def get_xz_plane_from_frame(
        self, frame: Frame, name: str | None = None
    ) -> PlaneFromFrame:
        name = self._get_name(name)
        rotated_frame = frame.get_rotated_frame_from_axis(
            frame.get_x_axis(), np.pi / 2, name
        )
        return PlaneFromFrame(rotated_frame, name)

    def get_yz_plane_from_frame(
        self, frame: Frame, name: str | None = None
    ) -> PlaneFromFrame:
        name = self._get_name(name)
        rotated_frame = frame.get_rotated_frame_from_axis(
            frame.get_y_axis(), np.pi / 2, name
        )
        return PlaneFromFrame(rotated_frame, name)

    # TODO plan from a point and a normal ?
    # TODO counter not great -> what if multiple plane factory ?


PlaneChildren.__annotations__["frame"] = Frame
PlaneChildren.__annotations__["name"] = StringParameter
