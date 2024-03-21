from types import MethodType


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
                if not isinstance(value, child_type):
                    raise TypeError(
                        f"{child_name} must be an instance of {child_type.__name__}"
                    )
                self._children[child_name] = value

            return setter

        for child_name, child_type in cls.__annotations__.items():
            # Bind the generated setter to the instance as a method
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

    def __init__(self, parent):
        self._parent = parent  # The parent Node instance
        self._children = {}  # Dictionary to store child nodes


""" 
IMPORTANT you will need to add this type of code after your node definition:

# Ensure proper reference for circular type hints at the end of the file
NodeAChildren.__annotations__["myB"] = NodeB
NodeBChildren.__annotations__["myA"] = NodeA
NodeBChildren.__annotations__["myFirstB"] = NodeB
NodeBChildren.__annotations__["mySecondB"] = NodeB

"""
