from foundation.rendering.material import Material
from foundation.geometry.tf_helper import TFHelper
from foundation.types.node_interface import NodeInterface
from foundation.types.roots import PartRoot, AssemblyRoot
import numpy as np
from numpy import ndarray
from foundation.geometry.plane import PlaneFactory
from foundation.geometry.transform3d import TransformMatrix


class CompOrAssy(NodeInterface):
    """Abstract parent class of Part and Assembly"""

    def __init__(self, root: PartRoot | AssemblyRoot):
        super().__init__()
        self.tfh = (
            TFHelper()
        )  # Parts or Assemblies have a tf helper to manage their transform
        self.head = root  # TODO change head to root
        self.pf = PlaneFactory()

    def list_nodes(self, types):
        """Convert recursive tree architecure of nodes into list of nodes"""
        return self.head.rec_list_nodes(types)

    def set_material(self, material: Material):
        """Set the material of the component"""
        self.head.children.set_material(material)

    def paint(self, color: str = "green"):
        """Paint the component"""
        material = self.head.children._children[
            "material"
        ]  # TODO maybe init to Material() in __init__?
        if material is None:
            material = Material()
        material.set_diffuse_color(color)
        self.head.children.set_material(material)

    def xy(self):
        """Return the XY plane of the component"""
        return self.head.get_or_create_plane("xy", prefix=self.id)

    def yz(self):
        """Return the YZ plane of the component"""
        return self.head.get_or_create_plane("yz", prefix=self.id)

    def xz(self):
        """Return the XZ plane of the component"""
        return self.head.get_or_create_plane("xz", prefix=self.id)

    def yx(self):
        """Return the YX plane of the component"""
        return self.head.get_or_create_plane("yx", prefix=self.id)

    def zx(self):
        """Return the ZX plane of the component"""
        return self.head.get_or_create_plane("zx", prefix=self.id)

    def zy(self):
        """Return the ZY plane of the component"""
        return self.head.get_or_create_plane("zy", prefix=self.id)

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

    def get_position(self) -> ndarray:
        """Return the position of the component"""
        return self.tfh.get_tf().get_position()

    def to_dag(self) -> dict:
        """Serialize a Directed Acyclic Graph (DAG) into a dictionary
        (id : {type, params, deps})
        recursive function.
        """
        return self.head.to_dag(ids_already_seen=set())
