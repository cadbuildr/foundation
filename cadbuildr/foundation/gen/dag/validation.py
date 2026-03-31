"""Cycle detection and DAG validation."""

from typing import Any, Dict, Callable, Optional


def _build_node_info(dag_dict: dict, node_type_id: int, link_field: str) -> dict:
    """Build node info map from DAG for a specific node type and link field."""
    node_info = {}
    for node_id, node in dag_dict.items():
        if node.get("type") == node_type_id:
            # Get node name if available
            name_node_id = node["deps"].get("name", "")
            name = dag_dict.get(name_node_id, {}).get("params", {}).get("value", "unknown")
            link_id = node["deps"].get(link_field)
            node_info[node_id] = {
                "name": name,
                link_field: link_id,
            }
    return node_info


def _dfs_follow_link(
    node_id: str,
    dag_dict: dict,
    node_type_id: int,
    link_field: str,
    visited: set,
    rec_stack: set,
    path: list
) -> tuple[bool, list]:
    """DFS following a specific link field in nodes of a specific type."""
    if node_id not in dag_dict:
        return False, []
    
    node = dag_dict[node_id]
    # Only check nodes of the specified type
    if node.get("type") != node_type_id:
        return False, []
    
    # If node is in recursion stack, we found a cycle
    if node_id in rec_stack:
        cycle_path = path + [node_id]
        return True, cycle_path
    
    # If already visited (but not in stack), no cycle through this path
    if node_id in visited:
        return False, []
    
    visited.add(node_id)
    rec_stack.add(node_id)
    
    # Follow the specified link field
    if "deps" in node and link_field in node["deps"]:
        link_id = node["deps"][link_field]
        if link_id and isinstance(link_id, str):
            has_cycle, cycle_path = _dfs_follow_link(
                link_id, dag_dict, node_type_id, link_field, visited, rec_stack, path + [node_id]
            )
            if has_cycle:
                rec_stack.remove(node_id)
                return True, cycle_path
    
    rec_stack.remove(node_id)
    return False, []


def has_link_cycle(
    dag: Dict[str, Any],
    node_type_name: str,
    link_field: str
) -> tuple[bool, list, dict]:
    """
    Check for cycles following a specific link field in nodes of a specific type.
    
    Args:
        dag: The DAG dictionary with 'DAG' key containing {node_id: node_content}
        node_type_name: Name of the node type to check
        link_field: Name of the field to follow (e.g., "top_frame")
    
    Returns:
        (has_cycle: bool, cycle_path: list, node_info: dict)
    """
    if "DAG" not in dag:
        return False, [], {}
    
    dag_dict = dag["DAG"]
    serializable_nodes = dag.get("serializableNodes", {})
    node_type_id = serializable_nodes.get(node_type_name, -1)
    if node_type_id == -1:
        return False, [], {}
    
    # Build node info map
    node_info = _build_node_info(dag_dict, node_type_id, link_field)
    
    # Check all nodes of the specified type
    for node_id, node in dag_dict.items():
        if node.get("type") == node_type_id:
            visited = set()
            rec_stack = set()
            has_cycle, cycle_path = _dfs_follow_link(
                node_id, dag_dict, node_type_id, link_field, visited, rec_stack, []
            )
            if has_cycle:
                return True, cycle_path, node_info
    
    return False, [], node_info


def print_node_hierarchy_report(dag: Dict[str, Any], node_info: dict, node_type_name: str, link_field: str):
    """Print detailed node hierarchy report for debugging."""
    print(f"\n{node_type_name.upper()} HIERARCHY REPORT:")
    for node_id, info in node_info.items():
        link_name = node_info.get(info[link_field], {}).get("name", "unknown") if info[link_field] else "None"
        print(f"  {node_id} ({info['name']}) -> {link_field}: {info[link_field]} ({link_name})")


def _dfs_general(node: str, dag_dict: dict, visited: set, rec_stack: set) -> bool:
    """DFS for general cycle detection."""
    # Skip if node doesn't exist in DAG
    if node not in dag_dict:
        return False
    
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
    node_content = dag_dict[node]
    if "deps" in node_content:
        for child in node_content["deps"].values():
            # If the child is a list, iterate over each element
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, str) and _dfs_general(item, dag_dict, visited, rec_stack):
                        return True
            elif isinstance(child, str):
                if _dfs_general(child, dag_dict, visited, rec_stack):
                    return True
    
    # Remove the node from the recursion stack
    rec_stack.remove(node)
    return False


def has_cycle(dag: Dict[str, Any]) -> bool:
    """
    Check if a directed acyclic graph (DAG) has a cycle.
    
    Args:
        dag: The DAG dictionary. Can be either:
            - Old format: dict of {node_id: node_content}
            - New format: dict with 'DAG' key containing {node_id: node_content}
    
    Returns:
        True if a cycle is detected, False otherwise.
    """
    # Handle new format (with 'DAG' key) or old format (direct dict)
    if "DAG" in dag:
        dag_dict = dag["DAG"]
    else:
        dag_dict = dag
    
    # Iterate through all nodes in the graph
    visited = set()
    for node in dag_dict:
        if node not in visited:
            rec_stack = set()
            if _dfs_general(node, dag_dict, visited, rec_stack):
                return True
    
    return False

