"""Assemblies as connect sequences (what a click-built assembly records).

A layout is plain JSON::

    {
      "inputs":   {name: {"widget": {...}, "default": value}},
      "bindings": {name: [[item_name, component_input], ...]},   # equal values
      "items": [
        {"name": "plate", "item": "stdlib:RodEndPlate", "inputs": {...}, "connect": None},
        {"name": "rod_a", "item": "stdlib:SmoothRod", "inputs": {...},
         "connect": {"own": "end_a", "target": ["plate", "rod_hole_a"], "dof": {}}},
        {"name": "motor_screw", "item": "stdlib:DIN912Screw", "inputs": {...},
         "connect": {"own": "head_seat", "target": ["plate", None]}, "fill_group": "motor"},
      ],
      "loops": [{"a": ["idler", "rod_hole_a"], "b": ["rod_b", "end_b"], "dof": {}}],
    }

Items are in dependency order; only the first is grounded (``connect:
None``). ``fill_group`` makes one part per member of the target's interface
group (``assembly.connect_all``), named ``<name>_<i>``. ``loops`` are
connects between placed parts (checked loop closures). No positions
anywhere: :func:`build_layout` places everything with ``ground`` /
``connect`` / ``connect_all``.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Callable, Dict, List, Optional

__all__ = [
    "build_layout",
    "derive_bindings",
    "item",
    "layout_part_names",
    "link",
    "validate_layout",
]


def link(own: Optional[str], target: List[Any], **dof: float) -> Dict[str, Any]:
    """The ``connect`` of an item: its interface ``own`` onto ``target``
    ``[item name, interface name]``, with joint values ``dof``."""
    return {
        "own": own,
        "target": list(target),
        "dof": {k: float(v) for k, v in dof.items()},
    }


def item(
    name: str,
    item_id: str,
    inputs: Dict[str, Any],
    connect: Optional[Dict[str, Any]] = None,
    fill_group: Optional[str] = None,
) -> Dict[str, Any]:
    out = {"name": name, "item": item_id, "inputs": dict(inputs), "connect": connect}
    if fill_group:
        out["fill_group"] = fill_group
    return out


def _resolve(item_id: str) -> Any:
    from .evaluate import resolve_item
    from .registry import find_item

    return find_item(item_id) or resolve_item(item_id)


def _build(entry: Dict[str, Any], name: str) -> Any:
    from ..gen.models import StringParameter
    from .registry import call_configurable

    component = call_configurable(_resolve(entry["item"]), entry["inputs"])
    component.name = StringParameter(value=name)
    return component


def _iface(component: Any, name: Optional[str]) -> Any:
    return component.interface(name) if name else component


def build_layout(layout: Dict[str, Any], assembly: Any = None) -> Any:
    """Build a layout with ``ground`` / ``connect`` / ``connect_all`` (no
    positions); returns the assembly, with ``assembly.parts`` = {name: part}."""
    from ..gen.models import Assembly

    asm = assembly if assembly is not None else Assembly()
    parts: Dict[str, Any] = {}
    for entry in layout["items"]:
        link_ = entry.get("connect")
        name = entry["name"]
        if link_ is None:
            if parts:
                raise ValueError(f"{name}: only the first item may be grounded")
            parts[name] = _build(entry, name)
            asm.ground(parts[name])
            continue
        target_name, target_iface = (list(link_["target"]) + [None])[:2]
        target = parts[target_name]
        dof = dict(link_.get("dof") or {})
        if entry.get("fill_group"):
            members = target.group(entry["fill_group"])
            made = [_build(entry, f"{name}_{i}") for i in range(len(members))]
            asm.connect_all(made, members, own=link_.get("own"), **dof)
            for i, part in enumerate(made):
                parts[f"{name}_{i}"] = part
            continue
        parts[name] = _build(entry, name)
        asm.connect(
            _iface(parts[name], link_.get("own")), _iface(target, target_iface), **dof
        )
    for loop in layout.get("loops") or []:
        a, b = loop["a"], loop["b"]
        asm.connect(
            _iface(parts[a[0]], a[1]),
            _iface(parts[b[0]], b[1]),
            **dict(loop.get("dof") or {}),
        )
    object.__setattr__(asm, "parts", parts)
    object.__setattr__(asm, "layout", layout)
    return asm


def layout_part_names(layout: Dict[str, Any], assembly: Any) -> List[str]:
    return list(assembly.parts)


def validate_layout(layout: Dict[str, Any]) -> None:
    """Shape rules: JSON, unique names, only the first item grounded, every
    target an earlier item, no positions."""
    json.dumps(layout)
    seen: List[str] = []
    for i, entry in enumerate(layout["items"]):
        extra = set(entry) - {"name", "item", "inputs", "connect", "fill_group"}
        if extra:
            raise ValueError(f"{entry['name']}: unexpected keys {sorted(extra)}")
        if entry["name"] in seen:
            raise ValueError(f"duplicate item {entry['name']}")
        if entry["connect"] is None and i:
            raise ValueError(f"{entry['name']}: only the first item may be grounded")
        if entry["connect"] is not None and entry["connect"]["target"][0] not in seen:
            raise ValueError(
                f"{entry['name']}: target {entry['connect']['target']} is not an earlier item"
            )
        seen.append(entry["name"])
    text = json.dumps(layout)
    for word in ('"translate"', '"rotate"', '"at"', '"rot_deg"'):
        if word in text:
            raise ValueError(f"layout carries a position ({word})")


def derive_bindings(
    fn: Callable[..., Dict[str, Any]],
    values: Dict[str, Any],
    probes: Dict[str, List[Any]],
) -> Dict[str, List[List[str]]]:
    """``{input: [[item, component input], ...]}`` for each top-level input:
    the component inputs that take the input's value as is (re-running the
    layout with each probe value). A component input that changes to a
    different value is derived, not bound: it is left out."""
    from ..interfaces import same_value

    base = {e["name"]: e for e in fn(**values)["items"]}
    out: Dict[str, List[List[str]]] = {}
    for name, options in probes.items():
        bound: Dict[tuple, bool] = {}
        for option in options:
            other = fn(**{**values, name: option})["items"]
            for e in other:
                b = base.get(e["name"])
                if b is None:
                    continue
                for key, value in e["inputs"].items():
                    if json.dumps(b["inputs"].get(key)) == json.dumps(value):
                        continue
                    ok = same_value(value, option) and same_value(
                        b["inputs"].get(key), values[name]
                    )
                    bound[(e["name"], key)] = bound.get((e["name"], key), True) and ok
        out[name] = [[n, k] for (n, k), ok in bound.items() if ok]
    return out
