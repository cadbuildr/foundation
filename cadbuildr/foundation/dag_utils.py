"""Utilities for creating and formatting DAG structures from Pydantic models."""

from typing import Any, Dict, List, Optional

from cadbuildr.foundation.constants import DEFAULT_TYPE_REGISTRY, DEFAULT_VALID_TYPES
from cadbuildr.foundation.gen.models import Part, Assembly
from cadbuildr.foundation.gen.dag import (
    format_dag,
    pydantic_to_dag,
    has_cycle,
    has_link_cycle,
)
from cadbuildr.foundation.gen.dag.validation import print_node_hierarchy_report
from cadbuildr.foundation.foundation_hooks import setup_foundation_hooks


def show_dag(obj: Any, valid_types: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Convert a Pydantic model to a formatted DAG ready for visualization.

    Args:
        obj: Pydantic model instance
        valid_types: Optional list of valid type names for expansion.
                     If None, uses DEFAULT_VALID_TYPES.

    Returns:
        Formatted DAG dictionary
    """
    # Convert Part/Assembly subclasses to their root representations
    # This ensures custom Part/Assembly classes get converted to PartRoot/AssemblyRoot
    if isinstance(obj, (Part, Assembly)):
        from cadbuildr.foundation.compute_functions import _convert_component_to_root

        obj = _convert_component_to_root(obj)

    # Set up foundation-specific hooks
    hooks = setup_foundation_hooks()

    memo: Dict[str, Any] = {}
    type_registry = {}

    # Build type registry from valid_types
    if valid_types is None:
        valid_types = DEFAULT_VALID_TYPES
        type_registry = DEFAULT_TYPE_REGISTRY.copy()
    else:
        # Create type registry from provided valid_types
        type_registry = {type_name: i for i, type_name in enumerate(valid_types)}

    root_id = pydantic_to_dag(obj, memo, type_registry, hooks)
    dag_data = format_dag(memo, root_id, type_registry)

    # Add serializableNodes mapping for frontend compatibility
    dag_data["serializableNodes"] = type_registry

    return dag_data


def show(obj: Any, valid_types: Optional[List[str]] = None) -> Optional[str]:
    """
    Show a CAD object by converting it to DAG and sending via WebRTC broker.

    Args:
        obj: Pydantic model instance to visualize
        valid_types: Optional list of valid type names. Nodes not in this list
                     will be expanded if possible.

    Returns:
        Request ID for tracking the build, or None if failed
    """
    try:
        from cadbuildr.foundation.coms.utils_webrtc import show_ext

        # Convert Part to PartRoot for viewer compatibility
        if isinstance(obj, Part):
            from cadbuildr.foundation.compute_functions import (
                _convert_component_to_root,
            )

            obj = _convert_component_to_root(obj)

        # Convert Assembly to AssemblyRoot
        if isinstance(obj, Assembly):
            # Import here to avoid circular dependency
            from cadbuildr.foundation.compute_functions import (
                _convert_component_to_root,
            )

            # Use _convert_component_to_root which handles frame hierarchy correctly
            obj = _convert_component_to_root(obj)

        dag = show_dag(obj, valid_types)

        # Check for cycles BEFORE sending to frontend (prevents infinite loops)
        # This is critical - frontend will infinite loop if there's a cycle in frame hierarchy
        has_cycle_bool, cycle_path, frame_info = has_link_cycle(
            dag, "Frame", "top_frame"
        )
        if has_cycle_bool:
            # Build detailed error message with frame names
            cycle_names = [
                frame_info.get(fid, {}).get("name", fid) for fid in cycle_path
            ]
            error_msg = (
                f"ERROR: Frame cycle detected in DAG!\n"
                f"  Cycle path (IDs): {' -> '.join(cycle_path)}\n"
                f"  Cycle path (names): {' -> '.join(cycle_names)}\n"
                f"  This will cause infinite loop in frontend. DAG not sent."
            )
            print("=" * 80)
            print("BUG DETECTED: Frame Cycle")
            print("=" * 80)
            print(error_msg)
            print_node_hierarchy_report(dag, frame_info, "Frame", "top_frame")
            print("=" * 80)
            raise ValueError(error_msg)

        if has_cycle(dag):
            error_msg = "ERROR: General cycle detected in DAG! This will cause infinite loop in frontend. DAG not sent."
            print("=" * 80)
            print("BUG DETECTED: General Cycle")
            print("=" * 80)
            print(error_msg)
            print("=" * 80)
            raise ValueError(error_msg)

        # Check for plane frames pointing to origin (will cause frontend infinite loop)
        frame_type_id = dag.get("serializableNodes", {}).get("Frame", -1)
        if frame_type_id != -1:
            for node_id, node in dag["DAG"].items():
                if node.get("type") == frame_type_id:
                    frame_name = (
                        dag["DAG"]
                        .get(node["deps"].get("name", ""), {})
                        .get("params", {})
                        .get("value", "")
                    )
                    top_frame_id = node["deps"].get("top_frame")
                    if frame_name in ["yx", "yz", "zy", "xz", "zx"] and top_frame_id:
                        top_frame = dag["DAG"].get(top_frame_id)
                        if top_frame:
                            top_frame_name = (
                                dag["DAG"]
                                .get(top_frame["deps"].get("name", ""), {})
                                .get("params", {})
                                .get("value", "")
                            )
                            if top_frame_name == "origin":
                                error_msg = (
                                    f"ERROR: Plane frame '{frame_name}' ({node_id}) points to 'origin' instead of component frame. "
                                    f"This will cause frontend infinite loop. DAG not sent."
                                )
                                print("=" * 80)
                                print("BUG DETECTED: Plane Frame Points to Origin")
                                print("=" * 80)
                                print(error_msg)
                                print("=" * 80)
                                raise ValueError(error_msg)

        request_id = show_ext(dag)
        return request_id
    except Exception as e:
        print(f"Error showing object: {e}")
        print("Make sure requests is installed: pip install requests")
        return None


# Backward compatibility aliases
def has_frame_cycle(dag: Dict[str, Any]) -> tuple[bool, list, dict]:
    """Backward compatibility alias for has_link_cycle with Frame type."""
    return has_link_cycle(dag, "Frame", "top_frame")


def print_frame_hierarchy_report(dag: Dict[str, Any], frame_info: dict):
    """Backward compatibility alias for print_node_hierarchy_report with Frame type."""
    return print_node_hierarchy_report(dag, frame_info, "Frame", "top_frame")


# Re-export for backward compatibility
__all__ = [
    "show",
    "show_dag",
    "format_dag",
    "pydantic_to_dag",
    "has_cycle",
    "has_link_cycle",
    "has_frame_cycle",  # Backward compat
    "print_node_hierarchy_report",
    "print_frame_hierarchy_report",  # Backward compat
]
