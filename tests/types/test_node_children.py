import pytest
from foundation.types.node_children import NodeChildren


class Node:
    children_class = NodeChildren  # Default; override in subclasses

    def __init__(self):
        self.children = self.children_class(self)


# Dummy node classes for testing
class NodeAChildren(NodeChildren):
    myB: "NodeB"


class NodeA(Node):
    children_class = NodeAChildren


class NodeBChildren(NodeChildren):
    myA: "NodeA"
    myFirstB: "NodeB"
    mySecondB: "NodeB"


class NodeB(Node):
    children_class = NodeBChildren


class NodeCChildren(NodeChildren):
    # No Children for NodeC
    pass


class NodeC(Node):
    children_class = NodeCChildren  # Assuming NodeC has specific children


# Without this the code will not work and the tests will fail
NodeAChildren.__annotations__["myB"] = NodeB
NodeBChildren.__annotations__["myA"] = NodeA
NodeBChildren.__annotations__["myFirstB"] = NodeB
NodeBChildren.__annotations__["mySecondB"] = NodeB


def test_setter_methods_created():
    node_a = NodeA()
    node_b = NodeB()

    # Check if the setter methods are created based on the annotations
    assert hasattr(
        node_a.children, "set_myB"
    ), "set_myB method should exist in NodeAChildren"
    assert hasattr(
        node_b.children, "set_myA"
    ), "set_myA method should exist in NodeBChildren"
    assert hasattr(
        node_b.children, "set_myFirstB"
    ), "set_myFirstB method should exist in NodeBChildren"
    assert hasattr(
        node_b.children, "set_mySecondB"
    ), "set_mySecondB method should exist in NodeBChildren"


def test_setter_methods_enforce_type_checks():
    node_a = NodeA()
    node_b = NodeB()

    with pytest.raises(TypeError):
        node_a.children.set_myB(
            node_a
        )  # Trying to set a NodeA where a NodeB is expected

    with pytest.raises(TypeError):
        node_b.children.set_myA(
            node_b
        )  # Trying to set a NodeB where a NodeA is expected

    # Proper type should not raise an error
    try:
        node_a.children.set_myB(NodeB())
        node_b.children.set_myA(NodeA())
    except TypeError:
        pytest.fail("Setter methods incorrectly enforce type checks")


def test_setter_methods_correctly_set_child_nodes():
    node_a = NodeA()
    node_b1 = NodeB()
    node_b2 = NodeB()

    # Set child nodes using the dynamically created setter methods
    node_a.children.set_myB(node_b1)
    node_b1.children.set_myA(node_a)
    node_b1.children.set_myFirstB(node_b2)

    # Verify that child nodes are correctly set
    assert (
        node_a.children._children["myB"] == node_b1
    ), "NodeB1 should be set as a child of NodeA"
    assert (
        node_b1.children._children["myA"] == node_a
    ), "NodeA should be set as a child of NodeB1"
    assert (
        node_b1.children._children["myFirstB"] == node_b2
    ), "NodeB2 should be set as myFirstB child of NodeB1"
