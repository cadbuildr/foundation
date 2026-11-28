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
from cadbuildr.foundation import source_capture


def _resolve_with_source(with_source: Optional[bool]) -> bool:
    """``None`` follows the capture switch (``CADBUILDR_WITH_SOURCE`` / enable())."""
    if with_source is None:
        return source_capture.is_enabled()
    return bool(with_source)


def show_dag(
    obj: Any,
    valid_types: Optional[List[str]] = None,
    with_source: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Convert a Pydantic model to a formatted DAG ready for visualization.

    Args:
        obj: Pydantic model instance
        valid_types: Optional list of valid type names for expansion.
                     If None, uses DEFAULT_VALID_TYPES.
        with_source: Emit ``src`` / ``fieldSrc`` (where each node was built in
                     user code) on the nodes. ``None`` follows
                     ``source_capture.is_enabled()``. Locations are recorded at
                     construction, so capture must have been on while the
                     model was built (see ``cadbuildr.foundation.source_capture``).

    Returns:
        Formatted DAG dictionary
    """
    with source_capture.suspended():
        return _show_dag(obj, valid_types, _resolve_with_source(with_source))


def _show_dag(
    obj: Any, valid_types: Optional[List[str]], with_source: bool
) -> Dict[str, Any]:
    # Assemblies built with interfaces (ground / connect) are checked on every
    # build; the issues travel with the DAG (``checks``) for the viewer.
    # Parts / assemblies with ``__checks__`` hooks or attached reports
    # (library DFM, printability, fits...) add theirs, from the whole tree.
    from cadbuildr.foundation.compute_functions import _SOURCE_COMPONENT_ATTR

    checks = None
    source = getattr(obj, _SOURCE_COMPONENT_ATTR, None) or obj
    if isinstance(source, (Part, Assembly)):
        from cadbuildr.foundation.checks import collect_checks
        from cadbuildr.foundation.interfaces import uses_interfaces

        found = collect_checks(source)
        if found or uses_interfaces(obj):
            checks = found

    # Convert Part/Assembly subclasses to their root representations
    # This ensures custom Part/Assembly classes get converted to PartRoot/AssemblyRoot
    if isinstance(obj, (Part, Assembly)):
        from cadbuildr.foundation.compute_functions import (  # pragma: allowlist secret
            _convert_component_to_root,
            _finalize_root_names,
        )

        obj = _convert_component_to_root(obj)
        _finalize_root_names(obj)

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

    root_id = pydantic_to_dag(obj, memo, type_registry, hooks, with_source=with_source)
    dag_data = format_dag(memo, root_id, type_registry)

    # Add serializableNodes mapping for frontend compatibility
    dag_data["serializableNodes"] = type_registry
    if checks is not None:
        dag_data["checks"] = checks

    return dag_data


def report_checks(checks: Optional[List[Dict[str, Any]]]) -> None:
    """Print ``assembly.check()`` issues to the run output (one line each,
    ``check: <severity> <code>: <message>``); info lines are skipped."""
    import sys

    for issue in checks or []:
        if issue.get("severity") == "info":
            continue
        fix = f" (fix: {issue['fix']})" if issue.get("fix") else ""
        sys.stdout.write(
            f"check: {issue['severity']} {issue['code']}: {issue['message']}{fix}\n"
        )


def show(
    obj: Any,
    valid_types: Optional[List[str]] = None,
    with_source: Optional[bool] = None,
) -> Optional[str]:
    """
    Show a CAD object by converting it to DAG and sending via WebRTC broker.

    Args:
        obj: Pydantic model instance to visualize
        valid_types: Optional list of valid type names. Nodes not in this list
                     will be expanded if possible.
        with_source: Emit ``src`` / ``fieldSrc`` on each node so viewer edits
                     map back to the user's code. ``None`` reads the capture
                     switch (``CADBUILDR_WITH_SOURCE=1`` or
                     ``source_capture.enable()``); see ``show_dag``.

    Returns:
        Request ID for tracking the build, or None if failed
    """
    try:
        from cadbuildr.foundation.coms.utils_webrtc import show_ext

        # Objects built while converting belong to serialization, not user code.
        with source_capture.suspended():
            # Convert Part/Assembly to PartRoot/AssemblyRoot for the viewer
            if isinstance(obj, (Part, Assembly)):
                # Import here to avoid circular dependency
                from cadbuildr.foundation.compute_functions import (  # pragma: allowlist secret
                    _convert_component_to_root,
                    _finalize_root_names,
                )

                # _convert_component_to_root handles frame hierarchy correctly
                obj = _convert_component_to_root(obj)
                _finalize_root_names(obj)

        dag = show_dag(obj, valid_types, with_source=with_source)
        report_checks(dag.get("checks"))

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
def has_frame_cycle(dag: Dict[str, Any]) -> tuple[bool, list[str], dict[str, Any]]:
    """Backward compatibility alias for has_link_cycle with Frame type."""
    return has_link_cycle(dag, "Frame", "top_frame")


def print_frame_hierarchy_report(
    dag: Dict[str, Any], frame_info: Dict[str, Any]
) -> None:
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
