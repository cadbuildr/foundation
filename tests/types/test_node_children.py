import pytest
from foundation.types.node_children import NodeChildren
from typing import Optional


class Node:
    children_class = NodeChildren  # Default; override in subclasses

    def __init__(self):
        self.children = self.children_class()


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


def test_getattr_accesses_child_nodes_correctly():
    node_a = NodeA()
    node_b = NodeB()

    # Set child nodes using the dynamically created setter methods
    node_a.children.set_myB(node_b)

    # Test __getattr__ method
    try:
        accessed_child = node_a.children.myB
        assert accessed_child is node_b, "Accessed child node should be node_b"
    except AttributeError:
        pytest.fail("Child nodes should be accessible as attributes")


def test_iter_yields_child_nodes_correctly():
    node_a = NodeA()
    node_b1 = NodeB()
    node_b2 = NodeB()

    # Set child nodes
    node_a.children.set_myB(node_b1)

    node_b1.children.set_myA(node_a)
    node_b1.children.set_myFirstB(node_b2)

    # Collect all children from node_b1 using __iter__
    collected_children = list(node_b1.children)

    # Verify that all child nodes are yielded correctly
    assert node_a in collected_children, "NodeA should be yielded by __iter__"
    assert node_b2 in collected_children, "NodeB2 should be yielded by __iter__"
    assert len(collected_children) == 2, "There should be exactly 2 child nodes yielded"


from typing import Union, List


class ShapeDummy(Node):
    pass


class CircleDummy(ShapeDummy):
    pass


class SquareDummy(ShapeDummy):
    pass


class CustomShapeDummy(ShapeDummy):
    pass


class ParameterDummy:
    pass


class FloatParameterDummy(ParameterDummy):
    pass


class BoolParameterDummy(ParameterDummy):
    pass


# Extending NodeChildren for testing Union types
class UnionTestChildren(NodeChildren):
    shape: Union[CircleDummy, SquareDummy]


# Extending NodeChildren for testing List types
class ListTestChildren(NodeChildren):
    shapes: List[SquareDummy]


class UnionTestNode(Node):
    children_class = UnionTestChildren


class ListTestNode(Node):
    children_class = ListTestChildren


UnionTestChildren.__annotations__["shape"] = Union[CircleDummy, SquareDummy]
ListTestChildren.__annotations__["shapes"] = List[SquareDummy]


def test_union_type_handling():
    union_node = UnionTestNode()

    # Testing valid Union types
    try:
        union_node.children.set_shape(CircleDummy())  # This should work
        union_node.children.set_shape(SquareDummy())  # This should also work
    except TypeError as e:
        pytest.fail(f"Union type handling failed: {e}")

    # Testing invalid Union type
    with pytest.raises(TypeError):
        union_node.children.set_shape(CustomShapeDummy())  # This should fail


class OtherUnionTypeChildren(NodeChildren):
    shape: CircleDummy | SquareDummy


class OtherUnionTypeNode(Node):
    children_class = OtherUnionTypeChildren


def test_other_union_type_handling():
    other_union_node = OtherUnionTypeNode()

    # Testing valid Union types
    try:
        other_union_node.children.set_shape(CircleDummy())  # This should work
        other_union_node.children.set_shape(SquareDummy())  # This should also work
    except TypeError as e:
        pytest.fail(f"Union type handling failed: {e}")

    # Testing invalid Union type
    with pytest.raises(TypeError):
        other_union_node.children.set_shape(CustomShapeDummy())  # This should fail


def test_list_type_handling():
    list_node = ListTestNode()

    # Testing valid List content
    try:
        list_node.children.set_shapes(
            [SquareDummy(), SquareDummy()]
        )  # This should work
    except TypeError as e:
        pytest.fail(f"List type handling failed: {e}")

    # Testing invalid List with different types
    with pytest.raises(TypeError):
        list_node.children.set_shapes(
            [CircleDummy(), SquareDummy()]
        )  # This should fail


class ListOfUnionChildren(NodeChildren):
    shapes: List[Union[CircleDummy, SquareDummy]]


class ListOfUnionNode(Node):
    children_class = ListOfUnionChildren


ListOfUnionChildren.__annotations__["shapes"] = List[Union[CircleDummy, SquareDummy]]


def test_list_of_union_type_handling():
    list_of_union_node = ListOfUnionNode()

    # Testing valid List content
    try:
        list_of_union_node.children.set_shapes(
            [CircleDummy(), SquareDummy()]
        )  # This should work
    except TypeError as e:
        pytest.fail(f"List of Union type handling failed: {e}")

    # Testing invalid List with different types
    with pytest.raises(TypeError):
        list_of_union_node.children.set_shapes(
            [CircleDummy(), CustomShapeDummy()]
        )  # This should fail


class OptionalTypeChildren(NodeChildren):
    shape: Optional[CircleDummy]


class OptionalTypeNode(Node):
    children_class = OptionalTypeChildren


OptionalTypeChildren.__annotations__["shape"] = Optional[CircleDummy]


def test_optional_type_handling():
    optional_node = OptionalTypeNode()

    optional_node.children.set_shape(CircleDummy())  # This should work
    optional_node.children.set_shape(None)  # This should also work

    # Testing invalid Optional type
    with pytest.raises(TypeError):
        optional_node.children.set_shape(SquareDummy())  # This should fail
