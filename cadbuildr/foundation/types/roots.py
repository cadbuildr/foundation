from cadbuildr.foundation.types.node import Node
from cadbuildr.foundation.types.parameters import (
    UnCastString,
    cast_to_string_parameter,
    StringParameter,
)
from cadbuildr.foundation.geometry.frame import Frame
from cadbuildr.foundation.geometry.plane import Plane
from cadbuildr.foundation.types.node_children import NodeChildren
from cadbuildr.foundation.operations import OperationTypes
from typing import List, Union
from cadbuildr.foundation.rendering.material import Material
from cadbuildr.foundation.geometry.transform3d import TransformMatrix
import numpy as np

PLANES_CONFIG = {
    "XY": {
        "xDir": [1, 0, 0],
        "normal": [0, 0, 1],
    },
    "YZ": {
        "xDir": [0, 1, 0],
        "normal": [1, 0, 0],
    },
    "ZX": {
        "xDir": [0, 0, 1],
        "normal": [0, 1, 0],
    },
    "XZ": {
        "xDir": [1, 0, 0],
        "normal": [0, -1, 0],
    },
    "YX": {
        "xDir": [0, 1, 0],
        "normal": [0, 0, -1],
    },
    "ZY": {
        "xDir": [0, 0, 1],
        "normal": [-1, 0, 0],
    },
    "front": {
        "xDir": [1, 0, 0],
        "normal": [0, 0, 1],
    },
    "back": {
        "xDir": [-1, 0, 0],
        "normal": [0, 0, -1],
    },
    "left": {
        "xDir": [0, 0, 1],
        "normal": [-1, 0, 0],
    },
    "right": {
        "xDir": [0, 0, -1],
        "normal": [1, 0, 0],
    },
    "top": {
        "xDir": [1, 0, 0],
        "normal": [0, 1, 0],
    },
    "bottom": {
        "xDir": [1, 0, 0],
        "normal": [0, -1, 0],
    },
}


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


def make_plane_getter(plane_name, config):
    def get_plane(self: BaseRoot) -> Plane:
        # Check if plane already exists
        for plane in self.children._children["planes"]:
            if plane.name == plane_name:
                return plane
        # Create the plane
        x_dir = np.array(config["xDir"], dtype=float)
        normal = np.array(config["normal"], dtype=float)
        point = np.array([0.0, 0.0, 0.0])
        frame = self._frame.from_xdir_and_normal(
            name=f"{plane_name}_frame",
            point=point,
            x_dir=x_dir,
            normal=normal,
        )
        plane = Plane(frame, plane_name)
        self.add_plane(plane)
        return plane

    method_name = plane_name.lower()
    get_plane.__name__ = method_name
    get_plane.__qualname__ = f"{BaseRoot.__name__}.{method_name}"
    return get_plane


def make_plane_getters(cls):
    for plane_name, config in PLANES_CONFIG.items():
        getter = make_plane_getter(plane_name, config)
        setattr(cls, getter.__name__, getter)


make_plane_getters(BaseRoot)


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
