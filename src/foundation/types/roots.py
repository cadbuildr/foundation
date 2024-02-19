from foundation.types.node import Node
from foundation.types.parameters import UnCastString, cast_to_string_parameter
from foundation.geometry.frame import OriginFrame


class BaseRoot(Node):
    def __init__(self, name: UnCastString | None = None, prefix: str = ""):
        super().__init__()
        self.origin_frame = OriginFrame()
        self.register_child(self.origin_frame)
        if name is None:
            name = prefix + str(self.id)
        self.name = cast_to_string_parameter(name)
        self.name.attach_to_parent(self)
        self.params = {"n_name": self.name.id}


class AssemblyRoot(BaseRoot):
    def __init__(self, name: UnCastString | None = None):
        super().__init__(name, "assembly_")


class ComponentRoot(BaseRoot):
    def __init__(self, name: UnCastString | None = None):
        super().__init__(name, "component_")
