"""Library-side mating: the code a viewer writes to connect two components.

* :func:`connect_request` -- ``{"a": side, "b": side, "dof"?, "assembly"?}``
  where a side is ``{"var", "interface"?, "item", "inputs"}``: builds both
  configurables, resolves the mate rule and returns the Mate (joint, flip,
  dof), the modifiers and the ``assembly.connect(...)`` line. A side without
  ``interface`` lists the compatible pairs (``candidates``).
* :func:`connect_line` -- the ``assembly.connect(...)`` / ``ground`` line of
  an insert.
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional

__all__ = ["connect_line", "connect_request", "rules_document"]


def _py(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return repr(float(value))
    return repr(value)


def connect_line(
    new_var: str,
    own: Optional[str],
    target: Optional[List[str]],
    dof: Optional[Dict[str, float]] = None,
    assembly: str = "assembly",
) -> str:
    """``assembly.connect(new.interface("own"), var.interface("x"), offset=...)``
    (``assembly.ground(new)`` without a target)."""
    if not target:
        return f"{assembly}.ground({new_var})"
    a = f'{new_var}.interface("{own}")' if own else new_var
    b = (
        f'{target[0]}.interface("{target[1]}")'
        if len(target) > 1 and target[1]
        else target[0]
    )
    extra = "".join(f", {k}={_py(v)}" for k, v in (dof or {}).items())
    return f"{assembly}.connect({a}, {b}{extra})"


def _build(side: Dict[str, Any]) -> Any:
    from .. import source_capture
    from .evaluate import resolve_item
    from .registry import call_configurable
    from .stamp import suspended as stamp_suspended

    item = resolve_item(str(side["item"]), side.get("module"), side.get("cls"))
    with source_capture.suspended(), stamp_suspended(), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return call_configurable(item, dict(side.get("inputs") or {}))


def connect_request(request: Dict[str, Any]) -> Dict[str, Any]:
    from ..interfaces import JOINTS, candidate_pairs, find_rule, spec_of
    from ..interfaces.rules import evaluate_rule

    a_side, b_side = request["a"], request["b"]
    asm = request.get("assembly") or "assembly"
    a, b = _build(a_side), _build(b_side)
    x = a.interface(a_side["interface"]) if a_side.get("interface") else a
    y = b.interface(b_side["interface"]) if b_side.get("interface") else b
    pairs, why = candidate_pairs(x, y)
    out: Dict[str, Any] = {
        "ok": True,
        "candidates": [
            {
                "a": p.anchor.name.value,
                "b": q.anchor.name.value,
                "a_type": p.type.value,
                "b_type": q.type.value,
            }
            for p, q in pairs
        ],
        "incompatible": why,
    }
    if len(pairs) != 1:
        out["ok"] = False
        out["error"] = (
            "no compatible interface pair"
            if not pairs
            else f"{len(pairs)} compatible pairs: name the interfaces"
        )
        return out
    p, q = pairs[0]
    rule, swapped = find_rule(p.type.value, q.type.value)
    mate, failures = evaluate_rule(rule, swapped, p, q, spec_of(p), spec_of(q))
    dof = {**mate.dof, **dict(request.get("dof") or {})}
    a_var, b_var = a_side.get("var") or "a", b_side.get("var") or "b"
    out.update(
        {
            "rule": rule.name,
            "joint": mate.joint,
            "jointType": JOINTS[mate.joint][0],
            "flip": mate.flip,
            "dof": dof,
            "dofNames": list(JOINTS[mate.joint][1]),
            "failures": failures,
            "modifiers": [
                {
                    "anchor": m.anchor.name.value,
                    "part": a_var if any(m.anchor is an for an in a.anchors) else b_var,
                    "operations": [type(op).__name__ for op in m.operations],
                }
                for m in mate.modifiers
            ],
            "code": connect_line(
                a_var,
                p.anchor.name.value,
                [b_var, q.anchor.name.value],
                request.get("dof"),
                asm,
            ),
        }
    )
    if failures:
        out["ok"] = False
        out["error"] = "; ".join(failures)
    return out


def rules_document(load_libraries: bool = True) -> Dict[str, Any]:
    """The rule table, after importing every installed library (their
    modules register their own interface types and rules)."""
    from ..interfaces import export_rules

    errors: List[str] = []
    if load_libraries:
        from .registry import discover
        from .sources import library_entry_points

        for root in sorted(library_entry_points()):
            try:
                discover(root, errors)
            except Exception as exc:  # pragma: no cover - a broken library
                errors.append(f"{root}: {type(exc).__name__}: {exc}")
    doc = export_rules()
    if errors:
        doc["errors"] = errors
    return doc
