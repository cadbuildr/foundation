from cadbuildr.foundation.types.node import Node
from cadbuildr.foundation.types.node_interface import NodeInterface
from cadbuildr.foundation.types.node_children import NodeChildren
from cadbuildr.foundation.geometry.frame import Frame
import numpy as np
from numpy import ndarray
from cadbuildr.foundation.types.parameters import (
    StringParameter,
    BoolParameter,
    cast_to_string_parameter,
    cast_to_bool_parameter,
    UnCastBool,
)
from cadbuildr.foundation.types.types_3d.point_3d import Point3D
from cadbuildr.foundation.exceptions import (
    InvalidParameterTypeException,
    InvalidParameterValueException,
)
from typing import Union, List


class PlaneChildren(NodeChildren):
    frame: "Frame"
    name: StringParameter
    display: BoolParameter


class Plane(Node):
    parent_types = []
    children_class = PlaneChildren

    def __init__(self, frame: Frame, name: str, display: UnCastBool = False):
        Node.__init__(self)
        self.children.set_frame(frame)
        self.children.set_name(cast_to_string_parameter(name))
        self.children.set_display(cast_to_bool_parameter(display))
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

    def get_parallel_plane(self, distance: float, name: str) -> "Plane":
        """return a plane parallel to the given plane at the given distance
        distance can be negative, it really is a translation in the direction of the normal
        """

        normal = self.get_normal()
        translated_frame = self.frame.get_translated_frame(
            name="f" + name, translation=normal * distance
        )
        return Plane(translated_frame, name)

    def get_angle_plane_from_axis(
        self, axis: ndarray, angle: float, name: str
    ) -> "Plane":
        """return the angle between the plane and the given axis"""
        # check_axis_is_on_plane(axis, plane) TODO
        rotated_frame = self.frame.get_rotated_frame_from_axis(axis, angle, "f" + name)
        return Plane(rotated_frame, name)


class PlaneFactory:
    def __init__(self):
        self.counter = 0

    def _get_name(self, name: str | None) -> str:
        if name is None:
            name = "plane_" + str(self.counter)
        self.counter += 1
        return name

    def get_parallel_plane(
        self, plane: Plane, distance: float, name: str | None = None
    ) -> Plane:
        return plane.get_parallel_plane(distance, self._get_name(name))

    def get_angle_plane_from_axis(
        self,
        plane: Plane,
        axis: Union[ndarray, List[int]],
        angle: float,
        name: str | None = None,
    ) -> Plane:
        """return a plane rotated around the given axis by the given angle
        axis must be on the frame"""
        if not isinstance(axis, ndarray):
            axis = np.array(axis)

        return plane.get_angle_plane_from_axis(axis, angle, self._get_name(name))

    def get_xy_plane_from_frame(self, frame: Frame, name: str | None = None) -> Plane:
        # xy is the default plane from the frame ( no need for any rotation)
        return Plane(frame, self._get_name(name))

    def get_xz_plane_from_frame(self, frame: Frame, name: str | None = None) -> Plane:
        name = self._get_name(name)
        rotated_frame = frame.get_rotated_frame_from_axis(
            frame.get_x_axis(), np.pi / 2, name
        )
        return Plane(rotated_frame, name)

    def get_yz_plane_from_frame(self, frame: Frame, name: str | None = None) -> Plane:
        name = self._get_name(name)
        rotated_frame = frame.get_rotated_frame_from_axis(
            frame.get_y_axis(), np.pi / 2, name
        )
        return Plane(rotated_frame, name)

    def get_plane_from_3_points(
        self, origin_frame: Frame, points: list[Point3D], name: str | None = None
    ) -> Plane:
        """return a plane from 3 points
        the frame will be oriented using [P1, P2] as the x axis and P1 as the origin
        the frame as an arg is the coordinate system in which the points are defined
        """
        if len(points) != 3:
            raise InvalidParameterTypeException(
                "points", points, "list of exactly three non aligned Point3D objects"
            )

        p1, p2, p3 = points

        # Create vectors from the points
        v1 = p2 - p1
        v2 = p3 - p1

        # Compute the normal to the plane
        normal = np.cross(v1.to_array(), v2.to_array())
        if np.linalg.norm(normal) == 0:
            if np.linalg.norm(v1.to_array()) == 0 or np.linalg.norm(v2.to_array()) == 0:
                raise InvalidParameterValueException(
                    "points", points, "at least two points are the same"
                )
            raise InvalidParameterValueException(
                "points", points, "the points are alligned"
            )
        normal /= np.linalg.norm(normal)

        # Create the frame using p1 as the origin and v1, v2 for the directions
        x_axis = v1.to_array() / np.linalg.norm(v1.to_array())
        y_axis = np.cross(normal, x_axis)
        y_axis /= np.linalg.norm(y_axis)  # cannot be 0

        name = "f_3dp_" + str(self.counter)

        # Create a Frame with origin p1 and axes x_axis, y_axis, normal
        origin = p1.to_array()
        frame = origin_frame.from_3dpoint_and_xy_axes(name, origin, x_axis, y_axis)
        plane = Plane(frame, "p_3dp_" + str(self.counter))
        self.counter += 1
        return plane

    # TODO plan from a point and a normal ?
    # TODO counter not great -> what if multiple plane factory ?


PlaneChildren.__annotations__["frame"] = Frame
PlaneChildren.__annotations__["name"] = StringParameter
