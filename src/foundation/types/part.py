from itertools import count
from foundation.sketch.sketch import Sketch
from foundation.types.comp_or_assy import CompOrAssy
from foundation.types.roots import PartRoot
from foundation.operations import OperationTypes, operation_types_tuple
from foundation.geometry.plane import Plane
import numpy as np


class Part(CompOrAssy):
    """
    A Part is a tree, with a head that is a node ( see Node type)
    #TODO Transform into a Node.
    """

    _ids = count(0)

    def __init__(self):
        name = "part" + str(next(self._ids))
        super().__init__(root=PartRoot(name))
        self.id = name

    def add_operation(self, op: OperationTypes):
        """Add an operation to the component
        @param op: Instance of one of the OperationTypes
        """
        if not isinstance(op, operation_types_tuple):
            raise Exception(
                "Operation must be an instance of OperationTypes = Union[Extrusion, Hole, Lathe, Fillet]"
            )
        self.head.add_operation(op)

    def add_operations(self, ops: list[OperationTypes]):
        """Add a list of operations to the component"""
        for op in ops:
            self.add_operation(op)

    def add_construction_element(self, name, element):
        """Add a construction element to the construction element dictionary to be used
        during the assembly"""
        self.construction_elements[name] = element

    def get_construction_element(self, name):
        """Get a construction element from the dictionary"""
        if name not in self.construction_elements:
            raise Exception("No construction element with name {}".format(name))
        return self.construction_elements.get(name)

    def get_operations(self):
        return self.head.get_children(type_filter=["Operation"])

    def get_sketches(self) -> list[Sketch]:
        return list(set(self.head.rec_list_nodes(type_filter=["Sketch"])))

    @classmethod
    def reset_ids(cls):
        """
        Resets the _ids counter to 0.
        """
        cls._ids = count(0)
