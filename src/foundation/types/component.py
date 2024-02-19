from typing import List
from itertools import count
from foundation.geometry.plane import PlaneFromFrame
from foundation.sketch.sketch import Sketch
from foundation.types.comp_or_assy import CompOrAssy
from foundation.geometry.frame import OriginFrame
from foundation.types.roots import ComponentRoot


class Component(CompOrAssy):
    """
    A Component is a tree, with a head that is a node ( see Node type)
    #TODO Transform into a Node.
    """

    _ids = count(0)

    def __init__(self):
        super().__init__()
        self.head = ComponentRoot()
        self.id = "part" + str(next(self._ids))

    def get_origin_frame(self) -> OriginFrame:
        origin = self.head.origin_frame
        # Check the type of the head TODO move this to the tests
        assert isinstance(origin, OriginFrame)
        return origin

    def get_sketch_from_plane(self, plane_node):
        # TODO move this ?
        for c in plane_node.children:
            if isinstance(c, Sketch):
                return c
        return None

    def add_operation(self, op):
        self.head.register_child(op)

    def add_operations(self, ops):
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

    def get_sketches(self):
        return list(set(self.head.rec_list_nodes(type_filter=["Sketch"])))

    def get_frames(self):
        frames = []
        if isinstance(self.head, OriginFrame):
            frames.append(self.head)
        frames += self.head.rec_list_nodes(type_filter=["Frame"])
        return frames

    def attach_operations(self):
        for o in self.get_operations():
            o.set_component_name(self.id)
