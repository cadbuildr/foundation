from cadbuildr.foundation.operations.base import Operation
from cadbuildr.foundation.types.node import Node
from cadbuildr.foundation.types.node_children import NodeChildren
from cadbuildr.foundation.operations import Extrusion, Lathe
from cadbuildr.foundation.types.parameters import (
    UnCastFloat,
    FloatParameter,
    cast_to_float_parameter,
)
from cadbuildr.foundation.finders.base import EdgeFinder


class ChamferChildren(NodeChildren):
    solid: Extrusion | Lathe
    radius: FloatParameter
    edge_finder: EdgeFinder


class Chamfer(Operation, Node):
    children_class = ChamferChildren

    def __init__(
        self,
        solid: Extrusion | Lathe,
        radius: UnCastFloat = 1.0,
        edge_finder: EdgeFinder | None = None,
    ):
        Operation.__init__(self)
        Node.__init__(self, parents=[])
        self.children.set_radius(cast_to_float_parameter(radius))
        self.children.set_solid(solid)
        if edge_finder is not None:
            self.children.set_edge_finder(edge_finder)

        self.radius = self.children.radius
        self.solid = self.children.solid
        self.edge_finder = self.children.edge_finder

        self.params = {}


ChamferChildren.__annotations__["solid"] = Extrusion | Lathe
ChamferChildren.__annotations__["radius"] = FloatParameter
ChamferChildren.__annotations__["edge_finder"] = EdgeFinder
