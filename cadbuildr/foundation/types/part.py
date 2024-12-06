from itertools import count
from cadbuildr.foundation.sketch.sketch import Sketch
from cadbuildr.foundation.types.comp_or_assy import CompOrAssy, AutoInitMeta
from cadbuildr.foundation.types.roots import PartRoot
from cadbuildr.foundation.operations import OperationTypes, operation_types_tuple
from cadbuildr.foundation.geometry.plane import Plane
import numpy as np
from typing import Optional


class Part(CompOrAssy, metaclass=AutoInitMeta):
    _ids = count(0)

    def __init__(self, name: Optional[str] = None, **kwargs):
        if name is None:
            name = "part" + str(next(self._ids))
        super().__init__(root=PartRoot(name), **kwargs)
        self.id = name
        self._part_init_called = True

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        original_init = cls.__init__

        def new_init(self, *args, **kwargs):
            Part.__init__(self)
            original_init(self, *args, **kwargs)

        cls.__init__ = new_init

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
