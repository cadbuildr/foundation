from cadbuildr.foundation.rendering.material import Material
from cadbuildr.foundation.geometry.tf_helper import TFHelper
from cadbuildr.foundation.types.node_interface import NodeInterface
from cadbuildr.foundation.types.roots import PartRoot, AssemblyRoot, PLANES_CONFIG
import numpy as np
from numpy import ndarray
from cadbuildr.foundation.geometry.plane import PlaneFactory
from cadbuildr.foundation.geometry.transform3d import TransformMatrix
from typing import Any, Dict, List, TypeVar, Protocol
from cadbuildr.foundation.geometry.plane import Plane

T = TypeVar("T")


class PlaneMethod(Protocol):
    def __call__(self: T) -> Plane: ...


# # This is a small trick to facilitate user to create a part without having to call super.
class AutoInitMeta(type):
    def __call__(cls, *args, **kwargs):
        obj = super().__call__(*args, **kwargs)
        if not hasattr(obj, "_part_init_called"):
            raise RuntimeError(
                f"__init__ method of {cls.__name__} must call super().__init__()"
            )
        return obj


class CompOrAssy(NodeInterface):
    """Abstract parent class of Part and Assembly"""

    xy: PlaneMethod
    yz: PlaneMethod
    xz: PlaneMethod
    yx: PlaneMethod
    zx: PlaneMethod
    zy: PlaneMethod
    front: PlaneMethod
    back: PlaneMethod
    left: PlaneMethod
    right: PlaneMethod
    top: PlaneMethod
    bottom: PlaneMethod

    def __init__(self, root: PartRoot | AssemblyRoot, **kwargs):
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

    def paint(self, color: str = "green", transparency: float = 0.5):
        """Paint the component"""
        material = self.head.children._children[
            "material"
        ]  # TODO maybe init to Material() in __init__?
        if material is None:
            material = Material()
        material.set_diffuse_color(color)
        # material.set_transparency(transparency)
        self.head.children.set_material(material)

    # tf helper methods
    def reset_tf(self, tf=None):
        """Reset the transform of the component"""
        if tf is None:
            self.tfh.set_init()
        else:
            self.tfh.set_tf(tf)

    def translate(self, translation: ndarray | List[float], rotate: bool = False):
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
        self,
        axis: ndarray | List[float] = np.array([0.0, 0.0, 1.0]),
        angle: float = np.pi / 2,
    ):
        """Rotate the component around axis, with given angle"""
        self.tfh.rotate(axis, angle)

    def get_tf(self) -> TransformMatrix:
        """Return the transform of the component"""
        return self.tfh.get_tf()

    def get_position(self) -> ndarray:
        """Return the position of the component"""
        return self.tfh.get_tf().get_position()

    def post_process_dag(
        self, dag: Dict[str, Dict[str, Any]], initial_length: int = 4
    ) -> Dict[str, Dict[str, Any]]:
        """
        Post-process the DAG to assign shorter unique IDs based on truncated SHA-256 hashes.

        Args:
            dag (dict): The original DAG with full SHA-256 hash IDs.
            initial_length (int): The initial number of characters to use for truncated IDs.

        Returns:
            dict: The processed DAG with truncated unique IDs.
        """

        def common_prefix_length(a: str, b: str) -> int:
            """
            Calculate the length of the common prefix between two strings.

            Args:
                a (str): First string.
                b (str): Second string.

            Returns:
                int: Length of the common prefix.
            """
            min_len = min(len(a), len(b))
            i = 0
            while i < min_len and a[i] == b[i]:
                i += 1
            return i

        def get_min_unique_prefixes(
            sorted_hashes: List[str], initial_length: int
        ) -> Dict[str, int]:
            """
            Determine the minimal unique prefix length for each hash.

            Args:
                sorted_hashes (list): List of sorted hash strings.
                initial_length (int): Starting length for prefixes.

            Returns:
                dict: Mapping from full hash to its minimal unique prefix length.
            """
            prefixes = {}
            n = len(sorted_hashes)
            for i in range(n):
                current_hash = sorted_hashes[i]
                # Initialize prefix length
                prefix_length = initial_length

                # Compare with previous hash
                if i > 0:
                    prev_hash = sorted_hashes[i - 1]
                    common_prev = common_prefix_length(current_hash, prev_hash)
                    prefix_length = max(prefix_length, common_prev + 1)

                # Compare with next hash
                if i < n - 1:
                    next_hash = sorted_hashes[i + 1]
                    common_next = common_prefix_length(current_hash, next_hash)
                    prefix_length = max(prefix_length, common_next + 1)

                # Ensure prefix_length does not exceed hash length
                prefix_length = min(prefix_length, len(current_hash))

                prefixes[current_hash] = prefix_length

            return prefixes

        def build_truncated_ids(
            sorted_hashes: List[str], prefixes: Dict[str, int]
        ) -> Dict[str, str]:
            """
            Assign truncated IDs based on minimal unique prefixes.

            Args:
                sorted_hashes (list): List of sorted hash strings.
                prefixes (dict): Mapping from full hash to prefix length.

            Returns:
                dict: Mapping from full hash to truncated ID.
            """
            truncated_ids = {}
            seen_truncated_ids = set()

            for hash_str in sorted_hashes:
                prefix_length = prefixes[hash_str]
                truncated_id = hash_str[:prefix_length]

                # Handle any unforeseen collisions by incrementing prefix length
                while truncated_id in seen_truncated_ids and truncated_id != hash_str:
                    prefix_length += 1
                    if prefix_length > len(hash_str):
                        raise ValueError(
                            f"Cannot truncate hash {hash_str} to a unique ID."
                        )
                    truncated_id = hash_str[:prefix_length]

                truncated_ids[hash_str] = truncated_id
                seen_truncated_ids.add(truncated_id)

            return truncated_ids

        def replace_ids_in_dag(
            original_dag: Dict[str, Dict[str, Any]], id_map: Dict[str, str]
        ) -> Dict[str, Dict[str, Any]]:
            """
            Replace full hash IDs with truncated IDs in the DAG.

            Args:
                original_dag (dict): Original DAG with full hash IDs.
                id_map (dict): Mapping from full hash to truncated ID.

            Returns:
                dict: Updated DAG with truncated unique IDs.
            """
            updated_dag = {}
            for full_hash, node in original_dag.items():
                truncated_id = id_map[full_hash]
                updated_node = {
                    "type": node["type"],
                    "params": node["params"],
                    "deps": {},
                }

                for dep_key, dep_value in node.get("deps", {}).items():
                    if isinstance(dep_value, list):
                        updated_node["deps"][dep_key] = [
                            id_map.get(dep, dep) for dep in dep_value
                        ]
                    else:
                        updated_node["deps"][dep_key] = id_map.get(dep_value, dep_value)

                updated_dag[truncated_id] = updated_node

            return updated_dag

        # Step 1: Sort all hashes
        sorted_hashes = sorted(dag.keys())

        # Step 2: Determine minimal unique prefix lengths
        prefixes = get_min_unique_prefixes(sorted_hashes, initial_length)

        # Step 3: Assign truncated IDs
        self.id_map = build_truncated_ids(sorted_hashes, prefixes)

        # Step 4: Replace IDs in the DAG
        truncated_dag = replace_ids_in_dag(dag, self.id_map)

        return truncated_dag

    def to_dag(self, memo: Dict = {}) -> Dict:
        """Serialize a Directed Acyclic Graph (DAG) into a dictionary
        (id : {type, params, deps})
        recursive function.
        """
        dag = self.head.to_dag(memo=memo)
        return self.post_process_dag(dag)

    def get_hash(self) -> str:
        """Return the hash of the component"""
        if hasattr(self, "id_map") and self.id_map is not None:
            return self.id_map[self.head.get_hash()]
        else:  # Fallback to full hash
            return self.head.get_hash()


def add_plane_methods_to_comp_or_assy(cls):
    for plane_name in PLANES_CONFIG.keys():
        method_name = plane_name.lower()

        def make_plane_method(method_name):
            def plane_method(self):
                # Delegate the call to self.head
                return getattr(self.head, method_name)()

            plane_method.__name__ = method_name
            plane_method.__qualname__ = f"{cls.__name__}.{method_name}"
            plane_method.__doc__ = f"Return the {plane_name} plane of the component."
            return plane_method

        # Capture method_name to avoid closure issues
        plane_method = make_plane_method(method_name)
        setattr(cls, method_name, plane_method)


# Apply the dynamic method addition to CompOrAssy
add_plane_methods_to_comp_or_assy(CompOrAssy)
