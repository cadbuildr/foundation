from foundation.types.node import Node
from foundation.types.parameters import (
    UnCastString,
    cast_to_string_parameter,
    StringParameter,
)
from foundation.geometry.frame import Frame
from foundation.geometry.plane import Plane
from foundation.types.node_children import NodeChildren
from foundation.operations import OperationTypes
from typing import List, Union
from foundation.rendering.material import Material
from foundation.geometry.transform3d import TransformMatrix
import numpy as np


class RootChildren(NodeChildren):
    frame: Frame
    name = StringParameter
    operations = List[OperationTypes]
    material = Material
    planes = List[Plane]


class BaseRoot(Node):
    """The Root of an Assembly or a Part holds the origin frame of the assembly or part."""

    children_class = RootChildren

    def __init__(self, name: UnCastString | None = None, prefix: str = ""):
        super().__init__()

        # by default the frame is the origin frame
        self.children.set_frame(Frame.make_origin_frame())
        if name is None:
            name = prefix + str(self.id)
        self.children.set_name(cast_to_string_parameter(name))
        self.children.set_operations([])
        self.children.set_planes([])

        # shortcuts
        self._frame = self.children.frame
        self.name = self.children._children[
            "name"
        ]  # There is weird bug with self.children.name
        self.material = self.children.material

        self.params = {}

    def add_operation(self, operation: OperationTypes):
        # Note this fails for some reason :
        # TODO (find bug)
        # self.children.operations.append(operation)
        self.children._children["operations"].append(operation)

    def add_plane(self, plane: Plane):
        self.children._children["planes"].append(plane)

    def get_or_create_plane(self, axis: str, prefix: str) -> Plane:
        """axis is xy, yx, xz, zx, yz, zy"""
        for plane in self.children._children["planes"]:
            if plane.name.endswith('_p" + axis'):
                return plane

        o = self.get_frame()
        if axis == "xy":
            frame = o
        elif axis == "xz":
            frame = o.get_rotated_frame_from_axis(o.get_x_axis(), np.pi / 2, "xz_f")
        elif axis == "yz":
            xz = self.get_or_create_plane("xz", prefix).frame
            frame = xz.get_rotated_frame_from_axis(o.get_y_axis(), np.pi / 2, "yz_f")
        elif axis == "yx":
            # x is actually in the negative y direction
            frame = o.get_rotated_frame_from_axis(o.get_z_axis(), np.pi / 2, "yx_f")
        elif axis == "zx":
            xz = self.get_or_create_plane("xz", prefix).frame
            frame = xz.get_rotated_frame_from_axis(o.get_y_axis(), np.pi / 2, "zx_f")
        elif axis == "zy":
            yz = self.get_or_create_plane("yz", prefix).frame
            frame = yz.get_rotated_frame_from_axis(o.get_x_axis(), np.pi / 2, "zy_f")
        # create the plane
        plane = Plane(frame, prefix + "_p" + axis)
        self.add_plane(plane)
        return plane

    def make_origin_frame_default_frame(
        self, id: str, new_tf: TransformMatrix, new_top_frame: Frame
    ):
        # Note this will only work once, so the the part/assembly can only be added once to a top assembly
        if self._frame.name.value == "origin":
            new_name = f"{id}_origin"
            # will be something like origin_i or origin_part_i
            self._frame.change_top_frame(
                new_top_frame=new_top_frame, new_name=new_name, new_tf=new_tf
            )
        else:
            print("Frame name is ", self._frame.name, " should be origin")
            assert False, "This should not happen"

    def get_frame(self) -> Frame:
        return self._frame

    def get_origin_planes(self) -> List[Plane]:
        return self.children._children["origin_planes"]


class PartRoot(BaseRoot):
    def __init__(self, name: UnCastString | None = None):
        super().__init__(name, "component_")


# adding the list of components as children of the AssemblyRoot
class AssemblyRootChildren(RootChildren):
    components = List[
        PartRoot
    ]  # TODO this is not great when assemblies contain sub assemblies


class AssemblyRoot(BaseRoot):
    children_class = AssemblyRootChildren

    def __init__(self, name: UnCastString | None = None):
        super().__init__(name, "assembly_")
        self.children.set_components([])

    def add_component(self, component: Union[PartRoot, "AssemblyRoot"]):
        self.children._children["components"].append(component)


RootChildren.__annotations__["frame"] = Frame
RootChildren.__annotations__["name"] = StringParameter
RootChildren.__annotations__["operations"] = List[OperationTypes]
RootChildren.__annotations__["material"] = Material
RootChildren.__annotations__["planes"] = List[Plane]

AssemblyRootChildren.__annotations__["frame"] = Frame
AssemblyRootChildren.__annotations__["name"] = StringParameter
AssemblyRootChildren.__annotations__["operations"] = List[OperationTypes]
AssemblyRootChildren.__annotations__["material"] = Material
AssemblyRootChildren.__annotations__["components"] = List[PartRoot]
AssemblyRootChildren.__annotations__["planes"] = List[Plane]
