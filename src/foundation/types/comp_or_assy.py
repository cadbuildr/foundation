from foundation.rendering.material import Material
from foundation.geometry.tf_helper import TFHelper
from foundation.types.node_interface import NodeInterface
from foundation.types.roots import ComponentRoot, AssemblyRoot
import numpy as np
from numpy import ndarray
from foundation.geometry.plane import PlaneFactory
from foundation.geometry.transform3d import TransformMatrix


class CompOrAssy(NodeInterface):
    """Abstract parent class of Component and Assembly"""

    def __init__(self, root: ComponentRoot | AssemblyRoot):
        super().__init__()
        self.construction_elements = {}
        self.material = None
        self.tfh = (
            TFHelper()
        )  # Components or Assemblies have a tf helper to manage their transform
        self.head = root  # TODO change head to root
        self.pf = PlaneFactory()

    def set_origin_planes(self, planes):
        """Set the origin planes of the component"""
        self.origin_planes = planes

    def list_nodes(self, types):
        """Convert recursive tree architecure of nodes into list of nodes"""
        return self.head.rec_list_nodes(types)

    def set_material(self, material: Material):
        """Set the material of the component"""
        self.head.register_child(material)
        material.attach_to_node(self.id)
        # TODO  Could make this redundent by using the parent from the material

    def paint(self, color: str = "green"):
        """Paint the component"""
        self.material = Material()
        self.material.set_diffuse_color(color)
        self.set_material(self.material)

    def xy(self):
        """Return the XY plane of the component"""
        return self.origin_planes[0]

    def yz(self):
        """Return the YZ plane of the component"""
        return self.origin_planes[1]

    def xz(self):
        """Return the XZ plane of the component"""
        return self.origin_planes[2]

    # tf helper methods
    def reset_tf(self, tf=None):
        """Reset the transform of the component"""
        if tf is None:
            self.tfh.set_init()
        else:
            self.tfh.set_tf(tf)

    def translate(self, translation: ndarray, rotate: bool = False):
        """Translate the component"""
        self.tfh.translate(translation, rotate)

    def translate_x(self, x: float, rotate: bool = False):
        """Translate the component along the x axis"""
        self.tfh.translate_x(x, rotate)

    def translate_y(self, y: float, rotate: bool = False):
        """Translate the component along the y axis"""
        self.tfh.translate_y(y, rotate)

    def translate_z(self, z: float, rotate: bool = False):
        """Translate the component along the z axis"""
        self.tfh.translate_z(z, rotate)

    def rotate(
        self, axis: ndarray = np.array([0.0, 0.0, 1.0]), angle: float = np.pi / 2
    ):
        """Rotate the component around axis, with given angle"""
        self.tfh.rotate(axis, angle)

    def get_tf(self) -> TransformMatrix:
        """Return the transform of the component"""
        return self.tfh.get_tf()

    def to_dict(self, serializable_nodes: dict[str, int]) -> dict:
        """Serialize a Directed Acyclic Graph (DAG) into a dictionary
        (key: {type, params, deps})
        recursive function.
        """
        self.attach_operations()
        return self.head.to_dict(serializable_nodes)
