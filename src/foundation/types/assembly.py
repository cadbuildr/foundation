from foundation.types.component import Component
import numpy as np
from numpy import ndarray

from foundation.geometry.transform3d import TransformMatrix
from itertools import count
from foundation.rendering.material import Material
from foundation.types.comp_or_assy import CompOrAssy
from foundation.types.roots import AssemblyRoot
from typing import Union


class Assembly(CompOrAssy):
    """
    An Assembly is also a tree structure containing components or other assemblies ( sub assembly)

    """

    _ids = count(0)

    def __init__(self):
        name = "assy" + str(next(self._ids))
        super().__init__(AssemblyRoot(name))
        self.components = []  # list of components/subassemblies
        # list of transform from origin frame to component origin frame.
        self.tf_list = []  # list[TransformMatrix]
        self.id = name

    # TODO rename to add_part or add_assy (both are possible)
    def add_component(
        self, component: Union[Component, "Assembly"], tf: TransformMatrix | None = None
    ):
        """Add a component to the assembly
        We first figure out the transform from the assembly root to the component root
        We change the Frame of the ComponentRoot and then register the
        ComponentRoot as a child of the assembly root.
        """
        if tf is None:
            tf = component.get_tf()
        if type(tf) == ndarray:
            tf = TransformMatrix(tf)
        # Modifying component directly ? Might not be the best.
        if tf is None:
            tf = TransformMatrix.get_identity()
        component.head.make_origin_frame_default_frame(
            id=component.id, new_tf=tf, new_top_frame=self.head.get_frame()
        )

        assert component.head.get_frame().name != "origin"
        self.head.add_component(component.head)
        # component.head.parents.append(self.head)
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

    def solve_joints(self, verbose: bool = False):
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

    @classmethod
    def reset_ids(cls):
        """
        Resets the _ids counter to 0.
        """
        cls._ids = count(0)
