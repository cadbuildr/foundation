from itertools import count
from .node_children import NodeChildren
from foundation.types.serializable import serializable_nodes


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

    def check_parent_type(self):
        raise DeprecationWarning("Using Deprecated method check_parent_type")
        """If the Node has a parent, we check that the parent is of the correct type,
        If not it can only be Frame (origin) ( the only root node )"""
        if len(self.parents) != 0:
            for pt, parent in zip(self.parent_types, self.parents):
                assert pt == type(parent).__name__
        else:
            assert type(self).__name__ == "Frame"

    def register_child(self, child: "Node"):
        """Adds a child to the list"""
        raise DeprecationWarning("Using Deprecated method register_child")
        if child not in self.children:
            # print("Registering child", child, " to ", self)
            self.children.append(child)

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

    def to_dag(
        self, ids_already_seen: set = set(), only_keep_serializable_nodes: bool = True
    ) -> dict:
        """
        Return the Direct Acyclig Graph (DAG) of this node and all it's children recursively
        result is a dictionary of dictionaries with keys the id of the node and the
        values the dictionary of the node (see to_dict function)
        """
        res = {}
        # add yourself if not already seen
        if self.id not in ids_already_seen:
            res[self.id] = self.to_dict(only_keep_serializable_nodes)
            ids_already_seen.add(self.id)
        # add all the children
        res.update(
            self.children.to_dag(
                ids_already_seen=ids_already_seen,
                only_keep_serializable_nodes=only_keep_serializable_nodes,
            )
        )
        return res

    def is_serializable(self):
        if type(self).__name__ in serializable_nodes.keys():
            return True, serializable_nodes[type(self).__name__]
        # look at all the parent classes
        for parent in type(self).__mro__:
            if parent.__name__ in serializable_nodes.keys():
                return True, serializable_nodes[parent.__name__]
        return False, None

    def to_dict(self, only_keep_serializable_nodes: bool = True) -> dict:
        """Current Node as a dictionary"""
        is_serializable, node_type = self.is_serializable()
        if only_keep_serializable_nodes and not is_serializable:
            raise TypeError(
                f"""Node type {type(self).__name__} is not serializable, make sure
                            to add it to the serializable_nodes dict in the serializable.py file."""
            )
        node_dict = {
            "type": node_type,
            "deps": self.children.get_as_dict_of_ids(),
            "params": self.params,
        }
        return node_dict

    def get_children(self, type_filter: list[str]):
        """return the children of the component, eventually filtered"""
        res = []
        collect_all = len(type_filter) == 0
        # check if we collect all nodes, or if the types match
        for c in self.children:
            if collect_all or len(list(set(c.get_types()) & set(type_filter))):
                res.append(c)
        return res

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
