"""Evaluate one configurable: ``{item, inputs}`` -> the DAG of ``show(Cls(**inputs))``."""

from __future__ import annotations

import importlib
import traceback
from typing import Any, Dict, List, Optional

from .registry import LibraryItem, call_configurable, discover, find_item, item_for

__all__ = ["evaluate", "resolve_item"]


def _candidate_roots(library_id: str) -> List[str]:
    from .sources import library_entry_points

    roots = [
        root
        for root, info in library_entry_points().items()
        if info["id"] == library_id
    ]
    name = library_id.replace("-", "_")
    roots += [f"cadbuildr.{name}", name]
    return list(dict.fromkeys(roots))


def resolve_item(
    item_id: str, module: Optional[str] = None, cls: Optional[str] = None
) -> LibraryItem:
    """Find a registered item, importing its module / library as needed."""
    if module and cls:
        obj: Any = importlib.import_module(module)
        for part in cls.split("."):
            obj = getattr(obj, part)
        found = item_for(obj)
        if found is not None:
            return found
    item = find_item(item_id)
    if item is not None:
        return item
    library_id, _, name = item_id.partition(":")
    errors: List[str] = []
    for root in _candidate_roots(library_id):
        try:
            discover(root, errors)
        except ImportError:
            continue
        item = find_item(item_id)
        if item is not None:
            return item
    raise LookupError(f"unknown library item {item_id!r}")


def evaluate(
    request: Dict[str, Any], with_source: bool = False, with_interfaces: bool = False
) -> Dict[str, Any]:
    """``{"item", "inputs", "module"?, "cls"?, "project"?, "interfaces"?}`` ->
    ``{"ok", "dag"|"error", "interfaces"?}`` (``interfaces``: what the built
    instance exposes, ``[{name, type, params, role, group, required}]``)."""
    try:
        if request.get("project"):
            from .sources import activate, purge

            activate(request["project"])
            purge()
        item = resolve_item(
            str(request.get("item", "")), request.get("module"), request.get("cls")
        )
        if item.kind == "operation":
            return {"ok": False, "error": "operations are not evaluable alone"}
        obj = call_configurable(item, dict(request.get("inputs") or {}))
        from ..dag_utils import show_dag

        dag = show_dag(obj, with_source=bool(request.get("with_source", with_source)))
        out = {"ok": True, "dag": dag}
        if with_interfaces or request.get("interfaces"):
            from .registry import describe_interfaces

            out["interfaces"] = describe_interfaces(obj)
        return out
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(limit=8),
        }
