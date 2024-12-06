from cadbuildr.foundation.types.serializable import serializable_nodes
from cadbuildr.foundation import Sketch, Frame, Plane, Part, Assembly
from cadbuildr.foundation.types.roots import AssemblyRoot, PartRoot, Node
import sys
from typing import Union

try:
    import websocket
except ImportError:
    # mock the websocket module for environments where it is not available
    from types import ModuleType

    class MockWebSocket(ModuleType):
        @staticmethod
        def create_connection(*args, **kwargs):
            raise ImportError("websocket not available")

    websocket = MockWebSocket("websocket")

DAG_VERSION_FORMAT = "2.0"
TYPE_LIST = [Sketch, AssemblyRoot, PartRoot, Frame, Plane]
#
# ID_TYPE_ALLOWED = [3, 14, 15, 5, 6]
ID_TYPE_ALLOWED = [serializable_nodes[t.__name__] for t in TYPE_LIST]

DISPLAY_TYPE = Union[Sketch, Assembly, Part, Frame, Plane]


def search_name_with_id(id: int) -> str:
    """Search the name of a serializable node with its id

    @param id: the id to search
    """
    for key, value in serializable_nodes.items():
        if value == id:
            return key
    return "Unknown"


def show_dag(x: DISPLAY_TYPE):
    dag = x.to_dag(memo={})
    comp_hash = x.get_hash()
    dag = format_dag(dag, comp_hash)
    return dag


def format_dag(dag: dict, comp_hash: str, check_display_type: bool = True) -> dict:
    """Format the DAG to include extra information :
    - the serializable nodes
    - format version
    - root node id

    @param dag: the DAG to format ( see to_dag functions.)
    """
    root_node_id = comp_hash

    if check_display_type:
        root_node_type_id = dag[root_node_id]["type"]

        if root_node_type_id not in ID_TYPE_ALLOWED:
            types_allowed = [search_name_with_id(id) for id in ID_TYPE_ALLOWED]
            raise TypeError(
                f"Error: You cannot show a {search_name_with_id(root_node_type_id)} object.\nYou can only show {{{ ', '.join(types_allowed) }}}"
            )

    return {
        "version": DAG_VERSION_FORMAT,
        "rootNodeId": root_node_id,
        "DAG": dag,
        "serializableNodes": serializable_nodes,
    }


def show(x: DISPLAY_TYPE) -> None:
    """Function that is actually mocked on
    server and browser, but not on the tests"""
    if sys.platform == "emscripten":
        pass  # is getting mocked
    else:
        dag = show_dag(x)

        try:
            from cadbuildr.foundation.utils_websocket import show_ext

            show_ext(dag)
        except Exception:
            print("WebSocket not available")


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


def reset_ids():
    Node.reset_ids()
    Part.reset_ids()
    Assembly.reset_ids()
