from foundation.types.node import Node
from foundation.types.parameters import (
    UnCastString,
    cast_to_string_parameter,
    StringParameter,
)
from foundation.geometry.frame import OriginFrame
from foundation.types.node_children import NodeChildren
from foundation.operations import OperationTypes
from typing import List
from foundation.rendering.material import Material


class RootChildren(NodeChildren):
    origin_frame: OriginFrame
    name = StringParameter
    operations = List[OperationTypes]
    material = Material


class BaseRoot(Node):
    """The Root of an Assembly or a Part holds the origin frame of the assembly or part."""

    children_class = RootChildren

    def __init__(self, name: UnCastString | None = None, prefix: str = ""):
        super().__init__()

        self.children.set_origin_frame(OriginFrame())
        if name is None:
            name = prefix + str(self.id)
        self.children.set_name(cast_to_string_parameter(name))
        self.children.set_operations([])

        # shortcuts
        self.origin_frame = self.children.origin_frame
        self.name = self.children._children[
            "name"
        ]  # There is weird bug with self.chidren.name

        self.params = {
            "n_name": self.name.id,
            "n_frame": self.origin_frame.id,
        }

    def add_operation(self, operation: OperationTypes):
        # Note this fails for some reason :
        # TODO (find bug)
        # self.children.operations.append(operation)
        self.children._children["operations"].append(operation)


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

    def add_component(self, component: ComponentRoot):
        self.children._children["components"].append(component)


RootChildren.__annotations__["origin_frame"] = OriginFrame
RootChildren.__annotations__["name"] = StringParameter
RootChildren.__annotations__["operations"] = List[OperationTypes]
RootChildren.__annotations__["material"] = Material

AssemblyRootChildren.__annotations__["origin_frame"] = OriginFrame
AssemblyRootChildren.__annotations__["name"] = StringParameter
AssemblyRootChildren.__annotations__["operations"] = List[OperationTypes]
AssemblyRootChildren.__annotations__["material"] = Material
AssemblyRootChildren.__annotations__["components"] = List[ComponentRoot]
