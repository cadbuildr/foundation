from cadbuildr.foundation.operations.base import Operation
from cadbuildr.foundation.types.node import Node
from cadbuildr.foundation.types.node_children import NodeChildren
from cadbuildr.foundation.operations import OperationTypes
from cadbuildr.foundation.types.parameters import UnCastFloat, FloatParameter
from cadbuildr.foundation.finders.base import FaceFinder


class ShellChildren(NodeChildren):
    solid: OperationTypes
    thickness: UnCastFloat
    face_finder: FaceFinder


class Shell(Operation, Node):
    children_class = ShellChildren

    def __init__(
        self,
        solid: OperationTypes,
        thickness: UnCastFloat = 1.0,
        face_finder: FaceFinder | None = None,
    ):
        Operation.__init__(self)
        Node.__init__(self, parents=[])
        self.children.set_thickness(thickness)
        self.children.set_solid(solid)
        if face_finder is not None:
            self.children.set_face_finder(face_finder)

        self.thickness = self.children.thickness
        self.solid = self.children.solid
        self.face_finder = self.children.face_finder

        self.params = {}


ShellChildren.__annotations__["solid"] = OperationTypes
ShellChildren.__annotations__["thickness"] = FloatParameter
ShellChildren.__annotations__["face_finder"] = FaceFinder
