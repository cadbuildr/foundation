from cadbuildr.foundation import Frame, Plane, Sketch, Square, show, Point
import pytest


def test_auto_registration():
    """
    Test that shapes created with a sketch context are automatically registered
    to that sketch's elements list.
    """
    frame = Frame.make_origin_frame()
    p = Plane(frame, "xy")
    s = Sketch(p)

    # Create a square using the sketch's origin
    # This should automatically register the square (or its resulting polygon) to the sketch
    sq = Square.from_center_and_side(s.origin, 40)

    # Verify that the sketch has elements
    print(f"Sketch elements count: {len(s.elements)}")

    # The square (or its expanded polygon) should be in the elements
    # Note: Square expands to Polygon, so we check for that
    found = False
    for el in s.elements:
        # Check if it's the square/polygon we created
        # We can check ID or properties
        if el == sq:
            found = True
            break

    assert (
        found
    ), "Square (or its result) was not automatically added to sketch elements"
    assert len(s.elements) > 0, "Sketch elements list is empty"

    # Verify DAG generation doesn't crash or explode
    from cadbuildr.foundation.dag_utils import show_dag

    dag = show_dag(s)
    print(f"DAG generated successfully. Nodes: {len(dag['DAG'])}")

    # Verify Sketch node has elements in DAG
    sketch_nodes = [
        n for n in dag["DAG"].values() if n["type"] == 8
    ]  # Type 8 is Sketch (usually)
    # Actually type ID might vary, let's check deps

    found_elements_in_dag = False
    for node in dag["DAG"].values():
        if "elements" in node["deps"] and len(node["deps"]["elements"]) > 0:
            found_elements_in_dag = True
            print(f"Found Sketch node with {len(node['deps']['elements'])} elements")
            break

    assert found_elements_in_dag, "No elements found in Sketch DAG node"
