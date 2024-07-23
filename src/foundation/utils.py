from foundation.types.component import Component
from foundation.types.assembly import Assembly
from foundation.types.serializable import serializable_nodes
from foundation.geometry.plane import PlaneFromFrame, PlaneFactory
import numpy as np
import sys

DAG_VERSION_FORMAT = "1.0"


# TODO clean this code to remove copy paste


def start_component() -> Component:
    """
    Start a component with an origin frame and 3 planes

    """
    # TODO remove the extra planes if they are not necessary and create on call.
    component = Component()
    # Add the 2 other frames
    o = component.head.get_frame()
    xz = o.get_rotated_frame_from_axis(o.get_x_axis(), np.pi / 2, "xz_f")
    yz = xz.get_rotated_frame_from_axis(o.get_y_axis(), np.pi / 2, "yz_f")

    pxy = PlaneFromFrame(o, component.id + "_pxy")
    pyz = PlaneFromFrame(yz, component.id + "_pyz")
    pxz = PlaneFromFrame(xz, component.id + "_pxz")

    component.head.children.set_origin_planes([pxy, pyz, pxz])
    return component


def start_assembly() -> Assembly:
    """
    Start an assembly with an origin frame and 3 planes
    """
    # TODO remove the extra planes if they are not necessary and create on call.
    assembly = Assembly()
    o = assembly.head.get_frame()
    xz = o.get_rotated_frame_from_axis(o.get_x_axis(), np.pi / 2, "xz_f")
    yz = xz.get_rotated_frame_from_axis(o.get_y_axis(), np.pi / 2, "yz_f")

    pxy = PlaneFromFrame(o, assembly.id + "_pxy")
    pyz = PlaneFromFrame(yz, assembly.id + "_pyz")
    pxz = PlaneFromFrame(xz, assembly.id + "_pxz")

    assembly.head.children.set_origin_planes([pxy, pyz, pxz])

    return assembly


def format_dag(dag: dict):
    """Format the DAG to include extra information :
    - the serializable nodes
    - format version
    - root node id

    @param dag: the DAG to format ( see to_dag functions.)
    """
    # first of the key :

    return {
        "version": DAG_VERSION_FORMAT,
        "rootNodeId": next(iter(dag.keys())),
        "DAG": dag,
        "serializableNodes": serializable_nodes,
    }


def show(component: Component) -> None:
    """Function that is actually mocked on
    server and browser, but not on the tests"""
    if sys.platform == "emscripten":
        pass  # is getting mocked
    else:
        pass


def show_with_params(comp_class, params):
    """Function that is actually mocked on
    server and browser, but not on the tests"""
    pass


def show_from_params(params):
    pass


def has_cycle(dag: dict) -> bool:
    """
    Check if a directed acyclic graph (DAG) has a cycle.

    @param dag: The directed acyclic graph (DAG) represented as a dictionary.
    """
    # Create a set to track the visited nodes
    visited = set()
    # Create a set to track the nodes currently in the recursion stack
    rec_stack = set()

    # Define a helper function for DFS
    def dfs(node):
        # If the node is already in the recursion stack, we found a cycle
        if node in rec_stack:
            return True
        # If the node is already visited, skip it
        if node in visited:
            return False

        # Mark the node as visited and add it to the recursion stack
        visited.add(node)
        rec_stack.add(node)

        # Recur for all the dependencies (children) of the node
        if "deps" in dag[node]:
            for child in dag[node]["deps"].values():
                # If the child is a list, iterate over each element
                if isinstance(child, list):
                    for item in child:
                        if dfs(item):
                            return True
                else:
                    if dfs(child):
                        return True

        # Remove the node from the recursion stack
        rec_stack.remove(node)
        return False

    # Iterate through all nodes in the graph
    for node in dag:
        if dfs(node):
            return True

    return False
