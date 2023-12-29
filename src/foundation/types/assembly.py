from foundation.types.node import Node
from foundation.types.component import Component
from foundation.geometry.frame import OriginFrame
import numpy as np

from foundation.gcs.constraints.joints_factory import JointFactory
from foundation.geometry.transform3d import TransformMatrix
from foundation.types.types import (
    UnCastString,
    cast_to_string_parameter,
)
from itertools import count
from foundation.rendering.material import Material
from foundation.types.comp_or_assy import CompOrAssy


class AssemblyHead(Node):
    def __init__(self, name: UnCastString = None):
        super().__init__()
        self.origin_frame = OriginFrame()
        self.register_child(self.origin_frame)
        if name is None:
            name = "assembly_" + str(self.id)
        self.name = cast_to_string_parameter(name)
        self.name.attach_to_parent(self)
        self.params = {"n_name": self.name.id}


class Assembly(CompOrAssy):
    """
    An Assembly is also a tree structure containing components or other assemblies ( sub assembly)

    """

    _ids = count(0)

    def __init__(self):
        super().__init__()
        self.components = []  # list of components/subassemblies
        # list of transform from origin frame to component origin frame.
        self.tf_list = []
        self.head = AssemblyHead()
        # self.joint_factory = JointFactory(self.joints_cluster_manager)
        self.id = "assy" + str(next(self._ids))

    def add_component(self, component: Component, tf: TransformMatrix = None):
        if tf is None:
            tf = component.get_tf()
        if type(tf) == np.ndarray:
            tf = TransformMatrix(tf)
        # Modifying component directly ? Might not be the best.
        if tf is None:
            tf = TransformMatrix.get_identity()
        if component.head.origin_frame.name == "origin":
            component.head.origin_frame.to_default_frame(
                self.head.origin_frame, component.id, tf
            )
        assert component.head.origin_frame.name != "origin"
        self.head.register_child(component.head)
        self.components.append(component)
        self.tf_list.append(tf)

    def add_joint(self, joint):
        """Adding a joint to the assembly
        A joint is just another node in the tree
        """
        # TODO change Assembly to be a real Node
        pass

    def add_construction_element(self, name, element):
        """Add a construction element to the construction element dictionary to be used
        during the assembly"""
        self.construction_elements[name] = element

    def get_construction_element(self, name):
        """Get a construction element from the dictionary"""
        if name not in self.construction_elements:
            raise Exception("No construction element with name {}".format(name))
        return self.construction_elements.get(name)

    def get_sketches(self):
        return list(set(self.head.rec_list_nodes(type_filter=["Sketch"])))

    def solve_joints(self, verbose=False):
        # TODO : GCS
        raise NotImplementedError("GCS not implemented yet")
        # self.joints_cluster_manager.solve(verbose=verbose)

    def pretty_print(self):
        """Print the assembly tree"""
        for c in self.components:
            if type(c) == Assembly:
                print("|--> Sub assembly")
                c.pretty_print()
            else:
                print(f"""{self.id} -> {[type(o) for o in c.get_operations()]}""")

    def attach_operations(self):
        """Attach operations to the assembly"""
        for c in self.components:
            c.attach_operations()
