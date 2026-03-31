"""DAG formatting utilities."""

from typing import Any, Dict

from .hash import _truncate_dag_hashes


DAG_VERSION_FORMAT = "2.0"


def format_dag(dag: dict, root_node_id: str, type_registry: Dict[str, int]) -> dict:
    """
    Format the DAG to include version information and root node.
    
    Args:
        dag: The DAG dictionary
        root_node_id: The ID of the root node
        type_registry: Mapping of type names to integer IDs
        
    Returns:
        Formatted DAG with version and metadata
    """
    # Truncate hashes for smaller DAG size
    truncated_dag, truncated_root_id = _truncate_dag_hashes(dag, root_node_id)
    
    return {
        "version": DAG_VERSION_FORMAT,
        "rootNodeId": truncated_root_id,
        "DAG": truncated_dag,
        "serializableNodes": type_registry
    }

