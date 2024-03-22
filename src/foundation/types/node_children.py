from types import MethodType
from typing import get_origin, get_args, Union, List


def is_union_type(tp):
    # Check for PEP 604 style union types (using | operator) in Python 3.10+
    if isinstance(tp, type):
        return False  # Direct types (including generic types like `list[int]`) are not unions.
    if get_origin(tp) is Union or str(get_origin(tp)).endswith("types.UnionType"):
        return True
    # Handle the Union and UnionType cases explicitly
    if hasattr(tp, "__origin__") and tp.__origin__ is Union:
        return True
    # For Python 3.10 and newer, check if it's the new union type using `types.UnionType`
    try:
        from types import UnionType

        if isinstance(tp, UnionType):
            return True
    except ImportError:
        pass  # UnionType is not available in versions before Python 3.10
    return False


class NodeChildrenMeta(type):
    """
    A metaclass for automatically generating setter methods for child nodes in NodeChildren instances.

    This metaclass dynamically creates setter methods based on the annotations defined in the NodeChildren
    subclasses. These annotations indicate the expected child types, using the format:
        child_name: ChildNodeType

    The generated setter methods enforce type checks to ensure that only instances of the specified child node types
    can be added as children. This approach allows for declarative specification of child node relationships
    while providing runtime type safety and reducing boilerplate code.

    Usage:
    - Define a NodeChildren subclass with annotations for each child node.
    - The NodeChildrenMeta metaclass automatically generates corresponding setter methods
      when the subclass is instantiated, allowing for type-safe addition of child nodes.
    """

    def __call__(cls, *args, **kwargs):
        instance = super().__call__(*args, **kwargs)

        def create_setter(child_name, child_type):
            def setter(self, value):
                origin_type = get_origin(child_type)
                if is_union_type(child_type):  # Handle Union types
                    union_types = get_args(child_type)
                    if not any(isinstance(value, t) for t in union_types):
                        union_type_names = [t.__name__ for t in union_types]
                        raise TypeError(
                            f"{child_name} must be an instance of one of {union_type_names} but got {type(value).__name__}"
                        )
                elif origin_type:  # Handle generic types like List
                    if not isinstance(value, origin_type):
                        raise TypeError(
                            f"{child_name} must be a {origin_type.__name__} but got {type(value).__name__}"
                        )
                    arg_types = get_args(child_type)
                    if arg_types and not all(
                        isinstance(item, arg_types[0]) for item in value
                    ):
                        raise TypeError(
                            f"All elements of {child_name} must be instances of {arg_types[0].__name__}"
                        )
                else:  # Handle non-generic, non-Union types
                    if not isinstance(value, child_type):
                        raise TypeError(
                            f"{child_name} must be an instance of {child_type.__name__} but got {type(value).__name__}"
                        )
                self._children[child_name] = value

            return setter

        instance._children = {child_name: None for child_name in cls.__annotations__}
        for child_name, child_type in cls.__annotations__.items():
            bound_setter = MethodType(create_setter(child_name, child_type), instance)
            setattr(instance, f"set_{child_name}", bound_setter)

        return instance


class NodeChildren(metaclass=NodeChildrenMeta):
    """
    A base class for managing child nodes of a Node instance, enhanced by the NodeChildrenMeta metaclass.

    NodeChildren serves as a container for child nodes of a specific Node, facilitating the management
    and organization of child nodes through dynamically generated setter methods. These methods are
    automatically created based on the child node type annotations defined in the subclasses of NodeChildren.

    Each Node subclass should define its corresponding NodeChildren subclass, specifying the possible
    child node types through annotations. The NodeChildrenMeta metaclass then generates setter methods
    for adding these child nodes, ensuring type safety and simplifying the child management process.

    Usage:
    - Subclass NodeChildren for each specific Node subclass, defining child node types through annotations.
    - The NodeChildren instance associated with a Node will have setter methods for each child, allowing
      for the addition of child nodes in a type-safe manner.
    """

    def __init__(self):
        pass

    def __getattr__(self, name):
        if name in self._children:
            return self._children[name]
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __setattr__(self, name, value):
        if name in self.__annotations__:
            self._children[name] = value
        else:
            super().__setattr__(name, value)

    def __iter__(self):
        return iter(filter(None, self._children.values()))

    def to_dag(
        self, ids_already_seen: set = set(), only_keep_serializable_nodes: bool = True
    ):
        if ids_already_seen is None:
            ids_already_seen = set()
        res = {}
        for _, c in self._children.items():
            if c is not None:
                # check if c is not a list
                if not isinstance(c, list):
                    c = [c]
                for child in c:
                    if child.id not in ids_already_seen:
                        res.update(
                            child.to_dag(
                                ids_already_seen=ids_already_seen,
                                only_keep_serializable_nodes=only_keep_serializable_nodes,
                            )
                        )
                        ids_already_seen.add(child.id)
        return res

    def get_as_dict_of_ids(self):
        res = {}
        for k, v in self._children.items():
            if v is not None:
                # check if a list
                if isinstance(v, list):
                    res[k] = [c.id for c in v]
                else:
                    res[k] = v.id
        return res


""" 
IMPORTANT you will need to add this type of code after your node definition:

# Ensure proper reference for circular type hints at the end of the file
NodeAChildren.__annotations__["myB"] = NodeB
NodeBChildren.__annotations__["myA"] = NodeA
NodeBChildren.__annotations__["myFirstB"] = NodeB
NodeBChildren.__annotations__["mySecondB"] = NodeB

"""
