from itertools import count
from .node_children import NodeChildren
from cadbuildr.foundation.types.serializable import serializable_nodes
import hashlib
import json
from typing import Dict, Optional


class Node(object):
    """
    Nodes of the Directed Acyclic Graph (DAG) representing parts and assemblies.
    The Node class is a base class meant to be inherited by all the nodes of the DAG:
    - Assembly
    - Part
    - Operations
    - Frame
    - Parameter (leaf of the tree)
    - Point

    a List of parents to the Node are provided, if it is empty, it means the Node is the Frame ("origin").

    A Node can also have parameters attached to it that will be used when converting to a dict.

    """

    parent_types: list[str] = (
        []
    )  # can be reimplemented in child classes to enforce a parent type to the Node
    _ids = count(0)  # used to generate unique ids for the node
    children_class = NodeChildren  # Default : overriden in child classes

    def __init__(self, parents: list["Node"] | None = None):
        """At Init we register the new node to all provided parents"""
        self.params: dict = {}
        # self.extra_params = {} # not used for now so i commented it out
        self.parents = parents
        # print(self.parents)
        self.children = self.children_class()
        # node id used to identify component  (maybe should be a UUID to keep state)
        self.id = next(self._ids)

        # Hashing store for to_dag
        self._hash: Optional[str] = None
        self._hash_content: Optional[dict] = None

    def rec_list_nodes(
        self, type_filter: list[str], include_only_interface: bool = True
    ):
        """Recursibely go through all the children and return a list of all the nodes of the provided types"""
        res = []
        collect_all = len(type_filter) == 0
        # check if we collect all nodes, or if the types match
        if collect_all or len(
            list(
                set(self.get_types(include_only_interface=include_only_interface))
                & set(type_filter)
            )
        ):
            res.append(self)
        for c in self.children:
            res += c.rec_list_nodes(type_filter)
        return res

    def to_dag(self, memo, only_keep_serializable_nodes: bool = True) -> dict:
        """
        Return the Direct Acyclig Graph (DAG) of this node and all it's children recursively
        result is a dictionary of dictionaries with keys the id of the node and the
        values the dictionary of the node (see to_dict function)
        """
        hash_content = self.get_content_for_hash(memo, only_keep_serializable_nodes)
        node_hash = self.compute_hash(hash_content)
        # If the node is already serialized, return the existing memo
        if node_hash in memo:
            return memo

        # otherwise, add the node to the memo all the children are already there
        memo[node_hash] = hash_content
        return memo

    def is_serializable(self):
        if type(self).__name__ in serializable_nodes.keys():
            return True, serializable_nodes[type(self).__name__]
        # look at all the parent classes
        for parent in type(self).__mro__:
            if parent.__name__ in serializable_nodes.keys():
                return True, serializable_nodes[parent.__name__]
        return False, None

    def get_children(self, type_filter: list[str]):
        """return the children of the component, eventually filtered"""
        res = []
        collect_all = len(type_filter) == 0
        # check if we collect all nodes, or if the types match
        for c in self.children:
            if collect_all or len(list(set(c.get_types()) & set(type_filter))):
                res.append(c)
        return res

    def get_content_for_hash(
        self, memo: Dict, only_keep_serializable_nodes: bool = True
    ):
        # Check if there already
        if hasattr(self, "_hash_content") and self._hash_content is not None:
            return self._hash_content
        # Collect node's type and parameters
        is_serializable, node_type = self.is_serializable()
        if only_keep_serializable_nodes and not is_serializable:
            raise TypeError(
                f"""Node type {type(self).__name__} is not serializable, make sure
                            to add it to the serializable_nodes dict in the serializable.py file."""
            )

        content = {
            "type": node_type,
            "params": self.params,
            "deps": self.children.to_dag(memo, only_keep_serializable_nodes),
        }
        self._hash_content = content
        return content

    def get_hash(self):
        return self._hash

    def compute_hash(self, hash_content: Dict):
        if self.get_hash() is not None:
            return self.get_hash()
        # Serialize content
        content_bytes = json.dumps(hash_content, sort_keys=True).encode("utf-8")
        # Compute SHA-256 hash
        node_hash = hashlib.sha256(content_bytes).hexdigest()
        # Store the hash in the node instance
        self._hash = node_hash
        return node_hash

    @classmethod
    def get_types(cls, include_only_interface: bool = True) -> list[str]:
        """return the inherited types as a list. Used for the compiler to work and check if one of the parent_types is in these classes
        If the node inherits from a nodeinterface we return these interfaces as well"""
        types = []
        for o in cls.mro():
            if (not include_only_interface) or (
                hasattr(o, "is_interface") and o.is_interface
            ):
                types.append(o.__name__)
            else:
                pass
        return types

    @classmethod
    def reset_ids(cls):
        """
        Resets the _ids counter to 0.
        """
        cls._ids = count(0)
