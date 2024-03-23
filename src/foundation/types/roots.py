from foundation.types.node import Node
from foundation.types.parameters import (
    UnCastString,
    cast_to_string_parameter,
    StringParameter,
)
from foundation.geometry.frame import Frame
from foundation.geometry.plane import PlaneFromFrame
from foundation.types.node_children import NodeChildren
from foundation.operations import OperationTypes
from typing import List, Union
from foundation.rendering.material import Material
from foundation.geometry.transform3d import TransformMatrix


class RootChildren(NodeChildren):
    frame: Frame
    name = StringParameter
    operations = List[OperationTypes]
    material = Material
    origin_planes = List[PlaneFromFrame]


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

        # shortcuts
        self._frame = self.children.frame
        self.name = self.children._children[
            "name"
        ]  # There is weird bug with self.chidren.name
        self.material = self.children.material

        self.params = {}

    def add_operation(self, operation: OperationTypes):
        # Note this fails for some reason :
        # TODO (find bug)
        # self.children.operations.append(operation)
        self.children._children["operations"].append(operation)

    def make_origin_frame_default_frame(
        self, id: str, new_tf: TransformMatrix, new_top_frame: Frame
    ):
        # Note this will only work once, so the the part/assembly can only be added once to a top assembly
        if self._frame.name == "origin":
            new_name = self.name.value + f"_{id}"
            # will be something like origin_i or origin_part_i
            self._frame.change_top_frame(
                new_top_frame=new_top_frame, new_name=new_name, new_tf=new_tf
            )
        else:
            print("Frame name is " + self._frame.name + " should be origin")
            assert False, "This should not happen"

    def get_frame(self) -> Frame:
        return self._frame

    def get_origin_planes(self) -> List[PlaneFromFrame]:
        return self.children._children["origin_planes"]


class ComponentRoot(BaseRoot):
    def __init__(self, name: UnCastString | None = None):
        super().__init__(name, "component_")


# adding the list of components as children of the AssemblyRoot
class AssemblyRootChildren(RootChildren):
    components = List[
        ComponentRoot
    ]  # TODO this is not great when assemblies contain sub assemblies


class AssemblyRoot(BaseRoot):
    children_class = AssemblyRootChildren

    def __init__(self, name: UnCastString | None = None):
        super().__init__(name, "assembly_")
        self.children.set_components([])

    def add_component(self, component: Union[ComponentRoot, "AssemblyRoot"]):
        self.children._children["components"].append(component)


RootChildren.__annotations__["frame"] = Frame
RootChildren.__annotations__["name"] = StringParameter
RootChildren.__annotations__["operations"] = List[OperationTypes]
RootChildren.__annotations__["material"] = Material
RootChildren.__annotations__["origin_planes"] = List[PlaneFromFrame]

AssemblyRootChildren.__annotations__["frame"] = Frame
AssemblyRootChildren.__annotations__["name"] = StringParameter
AssemblyRootChildren.__annotations__["operations"] = List[OperationTypes]
AssemblyRootChildren.__annotations__["material"] = Material
AssemblyRootChildren.__annotations__["components"] = List[ComponentRoot]
AssemblyRootChildren.__annotations__["origin_planes"] = List[PlaneFromFrame]
