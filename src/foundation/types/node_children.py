from types import MethodType
from typing import get_origin, get_args, Union, Dict, List


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


def check_value_against_type(value, expected_type):
    if is_union_type(expected_type):
        # Check if value matches any type in the Union
        return any(check_value_against_type(value, t) for t in get_args(expected_type))
    origin_type = get_origin(expected_type)
    if origin_type:
        # For parameterized generics like List[Type]
        if not isinstance(value, origin_type):
            return False
        arg_types = get_args(expected_type)
        if arg_types:
            if origin_type is list:
                # Check each item in the list
                item_type = arg_types[0]
                return all(check_value_against_type(item, item_type) for item in value)
            # Handle other generics if necessary (e.g., Dict, Tuple)
        return True
    else:
        # Non-generic, non-Union types
        return isinstance(value, expected_type)


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
                if not check_value_against_type(value, child_type):
                    # Generate a human-readable type name
                    def type_to_str(t):
                        if is_union_type(t):
                            return " | ".join(type_to_str(a) for a in get_args(t))
                        elif get_origin(t):
                            origin = get_origin(t)
                            args = ", ".join(type_to_str(a) for a in get_args(t))
                            return f"{origin.__name__}[{args}]"
                        else:
                            return t.__name__

                    expected_type_name = type_to_str(child_type)
                    raise TypeError(
                        f"{child_name} must be of type {expected_type_name}, but got {type(value).__name__}"
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

    def to_dag(
        self, memo: Dict, only_keep_serializable_nodes: bool = True
    ) -> Dict[str, str | List[str]]:
        """Add to the memo the relevant data and also
        returns a dict of hashes of the children"""
        # Collect children's hashes and add them to memo.
        children_hashes: Dict[str, str | List[str]] = {}
        for child_name, c in self._children.items():
            if c is not None:
                # check if c is not a list
                if not isinstance(c, list):
                    c.to_dag(memo, only_keep_serializable_nodes)
                    children_hashes[child_name] = c.get_hash()
                else:
                    c_hashes = []
                    for child in c:
                        child.to_dag(memo, only_keep_serializable_nodes)
                        c_hashes.append(child.get_hash())
                    children_hashes[child_name] = c_hashes
        return children_hashes


"""
IMPORTANT you will need to add this type of code after your node definition:

# Ensure proper reference for circular type hints at the end of the file
NodeAChildren.__annotations__["myB"] = NodeB
NodeBChildren.__annotations__["myA"] = NodeA
NodeBChildren.__annotations__["myFirstB"] = NodeB
NodeBChildren.__annotations__["mySecondB"] = NodeB

"""
