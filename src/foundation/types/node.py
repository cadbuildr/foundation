from itertools import count
from .node_children import NodeChildren


class Node(object):
    """
    Nodes of the Directed Acyclic Graph (DAG) representing parts and assemblies.
    The Node class is a base class meant to be inherited by all the nodes of the DAG:
    - Assembly
    - Component
    - Operations
    - Frame
    - Parameter (leaf of the tree)
    - Point

    a List of parents to the Node are provided, if it is empty, it means the Node is the OriginFrame.

    A Node can also have parameters attached to it that will be used when converting to a dict.

    """

    parent_types: list[str] = (
        []
    )  # can be reimplemented in child classes to enforce a parent type to the Node
    _ids = count(0)  # used to generate unique ids for the node
    children_class = NodeChildren  # Default : overriden in child classes

    def __init__(self, parents: list["Node"] | None = None):
        """At Init we register the new node to all provided parents"""
        self.params = {}
        # self.extra_params = {} # not used for now so i commented it out
        self.parents = parents
        # print(self.parents)
        self.children = self.children_class()
        # node id used to identify component  (maybe should be a UUID to keep state
        self.id = next(self._ids)
        # accross multiple compilations ... )
        # if self.parents is not None:
        #     for p in self.parents:
        #         p.register_child(self)

    def check_parent_type(self):
        """If the Node has a parent, we check that the parent is of the correct type,
        If not it can only be OriginFrame ( the only root node )"""
        if len(self.parents) != 0:
            for pt, parent in zip(self.parent_types, self.parents):
                assert pt == type(parent).__name__
        else:
            assert type(self).__name__ == "OriginFrame"

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

    def to_dict(self, serializable_nodes):
        # TODO remove serializable_nodes as a param as it can just be imported
        """Serialize a Directed Acyclic Graph (DAG) into a dict with
        (id_of_node:
            {'type': type_of_node, 'deps': [list_of_ids_of_children]}  #TODO convert list of ids of children
            to a dict that contains the parameter name of the children
        recursive function.
        """
        # print("GOING in : ", type(self), " my id is ", self.id)

        if type(self).__name__ not in serializable_nodes.keys():
            print(serializable_nodes.keys())
            raise TypeError(f"Node type {type(self).__name__} is not serializable")
        node_dict = {
            "type": serializable_nodes[type(self).__name__],
            # 'params':  TODO add the parameters of the node, if any
            "deps": [],
        }

        if self.params is not None:
            # TODO instead of using self.params,
            # we should generate self.params from the children
            # for this we need to have named children ( switch to dict instead of list)

            node_dict["params"] = self.params
        res = {}
        res[self.id] = node_dict

        # print("My children are ", self.children)
        for n in self.children:
            res.update(n.to_dict(serializable_nodes))
            node_dict["deps"].append(n.id)
        return res

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


class Orphan(Node):
    """
    Some nodes are always attached to the same type of parent
    ( for instance a sketch always has a plane as parent ).
    But for some nodes there could be many different types of parents that
    could be valid. For instance a parameter could be reused accross multiple
    parent nodes.
     For these nodes we don't explicitely write the type of the
     parents in the class definition.

     Parents can be added dynamically to the node.
    """

    def __init__(self):
        super().__init__(parents=[])
        # No parents are defined in init

    def attach_to_parent(self, parent: Node):
        """Attach the node to the parent"""
        raise DeprecationWarning("Using Deprecated method attach_to_parent")
        if self.parents is not None and parent not in self.parents:
            # print("adding parent")
            self.parents.append(parent)
            parent.register_child(self)
